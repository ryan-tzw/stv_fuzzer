"""Parallel fuzzer launcher.

Runs multiple independent fuzzer worker processes with isolated run directories.
This is intentionally lightweight: each worker is a normal fuzzer invocation,
which keeps core engine logic unchanged.
"""

import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from fuzzer.config import FuzzerConfig


def run_parallel(config: FuzzerConfig, workers: int) -> int:
    """Launch *workers* subprocesses and wait for completion.

    Returns a process-style exit code:
    - 0 if all workers exit successfully
    - 1 if any worker exits non-zero
    """
    if workers <= 1:
        raise ValueError("workers must be > 1 for parallel mode")

    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = config.runs_dir / "parallel" / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    procs: list[tuple[int, subprocess.Popen[bytes], Path, Path, BinaryIO]] = []
    console = Console()

    for worker_id in range(workers):
        worker_dir = session_dir / f"worker_{worker_id}"
        worker_dir.mkdir(parents=True, exist_ok=True)

        log_path = session_dir / f"worker_{worker_id}.log"
        status_path = session_dir / f"worker_{worker_id}.status.json"
        log_file = log_path.open("wb")

        cmd = _build_worker_cmd(config, worker_dir)
        env = os.environ.copy()
        env["STV_FUZZER_STATUS_FILE"] = str(status_path)
        proc = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd=str(Path.cwd()),
            env=env,
        )

        procs.append((worker_id, proc, log_path, status_path, log_file))

    start_time = time.monotonic()
    interrupted = False
    try:
        with Live(
            _render_dashboard(procs, session_dir, start_time),
            console=console,
            refresh_per_second=4,
        ) as live:
            while True:
                live.update(_render_dashboard(procs, session_dir, start_time))
                if all(proc.poll() is not None for _, proc, _, _, _ in procs):
                    break
                time.sleep(0.25)
    except KeyboardInterrupt:
        interrupted = True
        print("\n[parallel] Ctrl+C received, stopping workers...", file=sys.stderr)
        _graceful_stop_workers(procs)

    failed = False
    for worker_id, proc, log_path, _, log_file in procs:
        exit_code = proc.wait()
        log_file.close()
        if interrupted:
            continue
        if exit_code != 0:
            failed = True
            print(
                f"[parallel] worker {worker_id} exited with {exit_code} "
                f"(log: {log_path})",
                file=sys.stderr,
            )

    if interrupted:
        print(f"[parallel] stopped by user (session: {session_dir})")
        return 0

    if failed:
        print(f"[parallel] session dir: {session_dir}", file=sys.stderr)
        return 1

    print(f"[parallel] all workers completed successfully (session: {session_dir})")
    return 0


def _graceful_stop_workers(
    procs: list[tuple[int, subprocess.Popen[bytes], Path, Path, BinaryIO]],
    grace_seconds: float = 5.0,
) -> None:
    # First ask all running workers to stop cleanly (their engine handles
    # KeyboardInterrupt and executes stop/finalization).
    for _, proc, _, _, _ in procs:
        if proc.poll() is None:
            try:
                proc.send_signal(signal.SIGINT)
            except Exception:
                pass

    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        if all(proc.poll() is not None for _, proc, _, _, _ in procs):
            return
        time.sleep(0.1)

    # Fall back to terminate/kill if any worker ignored SIGINT.
    for _, proc, _, _, _ in procs:
        if proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        if all(proc.poll() is not None for _, proc, _, _, _ in procs):
            return
        time.sleep(0.1)

    for _, proc, _, _, _ in procs:
        if proc.poll() is None:
            try:
                proc.kill()
            except Exception:
                pass


def _render_dashboard(
    procs: list[tuple[int, subprocess.Popen[bytes], Path, Path, BinaryIO]],
    session_dir: Path,
    start_time: float,
) -> Panel:
    elapsed = int(time.monotonic() - start_time)

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Worker", justify="right")
    table.add_column("Status")
    table.add_column("Iter", justify="right")
    table.add_column("Corpus", justify="right")
    table.add_column("Crashes", justify="right")
    table.add_column("Exec/s", justify="right")
    table.add_column("Log")

    for worker_id, proc, log_path, status_path, _ in procs:
        status = _worker_status(proc)
        snap = _parse_worker_status(status_path, log_path)
        table.add_row(
            str(worker_id),
            status,
            snap["iterations"],
            snap["corpus"],
            snap["crashes"],
            snap["execs_per_s"],
            log_path.name,
        )

    running = sum(1 for _, proc, _, _, _ in procs if proc.poll() is None)
    title = (
        f"[bold blue]Parallel Fuzzer[/bold blue] "
        f"workers={len(procs)} running={running} elapsed={elapsed}s"
    )
    subtitle = f"session: {session_dir}"

    return Panel(table, title=title, subtitle=subtitle, border_style="blue")


def _worker_status(proc: subprocess.Popen[bytes]) -> str:
    code = proc.poll()
    if code is None:
        return "running"
    if code == 0:
        return "done"
    return f"failed({code})"


def _parse_worker_log(log_path: Path) -> dict[str, str]:
    text = _tail_text(log_path)
    return {
        "iterations": _last_match(text, r"Iterations:\s*(\d+)", "-"),
        "corpus": _last_match(text, r"Corpus size:\s*(\d+)", "-"),
        "crashes": _last_match(text, r"Unique crashes:\s*(\d+)", "-"),
        "execs_per_s": _last_match(text, r"Exec/s:\s*([0-9]+(?:\.[0-9]+)?)", "-"),
    }


def _parse_worker_status(status_path: Path, log_path: Path) -> dict[str, str]:
    if status_path.exists():
        try:
            payload = json.loads(status_path.read_text(encoding="utf-8"))
            return {
                "iterations": str(payload.get("iteration", "-")),
                "corpus": str(payload.get("corpus_size", "-")),
                "crashes": str(payload.get("unique_crashes", "-")),
                "execs_per_s": str(payload.get("execs_per_s", "-")),
            }
        except Exception:
            pass

    return _parse_worker_log(log_path)


def _tail_text(path: Path, max_bytes: int = 24000) -> str:
    if not path.exists():
        return ""
    data = path.read_bytes()
    if len(data) > max_bytes:
        data = data[-max_bytes:]
    return data.decode("utf-8", errors="replace")


def _last_match(text: str, pattern: str, default: str) -> str:
    matches = re.findall(pattern, text)
    if not matches:
        return default
    return matches[-1]


def _build_worker_cmd(config: FuzzerConfig, worker_runs_dir: Path) -> list[str]:
    """Construct a standalone CLI invocation for one worker."""
    cmd = [
        sys.executable,
        "-m",
        "fuzzer",
        "--project-dir",
        str(config.project_dir),
        "--harness",
        config.harness,
        "--corpus",
        config.corpus,
        "--mode",
        config.mode,
        "--runs-dir",
        str(worker_runs_dir),
        "--parallel-workers",
        "1",
        "--scheduler",
        config.scheduler,
        "--mutation-strategy",
        config.mutation_strategy,
        "--energy-c",
        str(config.energy_c),
        "--max-energy",
        str(config.max_energy),
    ]

    if config.max_iterations is None:
        cmd.extend(["--max-iterations", "-1"])
    else:
        cmd.extend(["--max-iterations", str(config.max_iterations)])

    if config.time_limit is None:
        cmd.extend(["--time-limit", "-1"])
    else:
        cmd.extend(["--time-limit", str(config.time_limit)])

    for arg in config.harness_args:
        cmd.append(f"--harness-arg={arg}")

    if config.blackbox_binary is not None:
        cmd.extend(["--blackbox-binary", str(config.blackbox_binary)])
        cmd.append(f"--blackbox-input-flag={config.blackbox_input_flag}")
        for arg in config.blackbox_args:
            cmd.append(f"--blackbox-arg={arg}")

    return cmd
