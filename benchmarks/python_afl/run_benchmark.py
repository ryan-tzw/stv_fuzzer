#!/usr/bin/env python3
"""Drive ``py-afl-fuzz`` against one or all python-afl baseline harnesses.

Layout produced per invocation::

    <out_root>/
      <target>/
        run0/           # AFL output root (contains default/{plot_data,crashes,...})
        run0.log        # py-afl-fuzz stderr/stdout
        run0.plot.csv   # normalized plot data (see parse_plot_data.py)
        run0.summary.json
        run1...
      meta.json         # run parameters (cmdline, seconds, runs, targets)

Run sequentially — AFL pins a core and parallel runs make ``execs/sec``
meaningless for comparison.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SEEDS_ROOT = _REPO_ROOT / "benchmarks" / "python_afl" / "seeds"
_VENV_PY = _REPO_ROOT / ".venv-python-afl" / "bin" / "python"
_VENV_PY_AFL_FUZZ = _REPO_ROOT / ".venv-python-afl" / "bin" / "py-afl-fuzz"
_TOOLS = _REPO_ROOT / "tools"
_PARSE_PLOT = _REPO_ROOT / "benchmarks" / "python_afl" / "parse_plot_data.py"
_SUMMARIZE = _TOOLS / "summarize_python_afl_artifacts.py"

TARGETS = {
    "json": "fuzz_json_python_afl.py",
    "ipv4": "fuzz_ipv4_python_afl.py",
    "ipv6": "fuzz_ipv6_python_afl.py",
    "cidrize_ipv4": "fuzz_cidrize_ipv4_python_afl.py",
    "cidrize_ipv6": "fuzz_cidrize_ipv6_python_afl.py",
}

# Env vars baked from the previous run logs + macOS AFL++ requirements.
AFL_ENV = {
    "AFL_SKIP_BIN_CHECK": "1",
    "AFL_SKIP_CPUFREQ": "1",
    "AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES": "1",
    "AFL_NO_UI": "1",
    "AFL_DUMB_FORKSRV": "1",
}


def _preflight() -> None:
    missing: list[str] = []
    for p in [_VENV_PY, _VENV_PY_AFL_FUZZ, _PARSE_PLOT, _SUMMARIZE]:
        if not p.exists():
            missing.append(str(p))
    if missing:
        sys.exit(
            "Missing required files:\n  "
            + "\n  ".join(missing)
            + "\nSee benchmarks/python_afl/README.md for setup instructions."
        )
    if shutil.which("afl-fuzz") is None:
        sys.exit(
            "afl-fuzz not on PATH. Install AFL++ (macOS: `brew install afl-fuzz`)."
        )


def _run_single(
    target: str,
    run_k: int,
    seconds: int,
    out_root: Path,
    seeds_override: Path | None,
) -> dict:
    harness = _TOOLS / TARGETS[target]
    if not harness.exists():
        raise FileNotFoundError(f"harness missing: {harness}")

    seeds = seeds_override if seeds_override is not None else (_SEEDS_ROOT / target)
    if not seeds.is_dir() or not any(seeds.iterdir()):
        raise FileNotFoundError(f"seeds dir empty or missing: {seeds}")

    run_dir = out_root / target / f"run{run_k}"
    log_path = out_root / target / f"run{run_k}.log"
    plot_csv = out_root / target / f"run{run_k}.plot.csv"
    summary_json = out_root / target / f"run{run_k}.summary.json"
    run_dir.parent.mkdir(parents=True, exist_ok=True)

    if run_dir.exists():
        shutil.rmtree(run_dir)

    cmd = [
        str(_VENV_PY_AFL_FUZZ),
        "-i",
        str(seeds),
        "-o",
        str(run_dir),
        "-V",
        str(seconds),
        "--",
        str(_VENV_PY),
        str(harness),
    ]

    env = dict(os.environ)
    env.update(AFL_ENV)

    print(f"[{target} run{run_k}] launching: {shlex.join(cmd)}")
    start = time.time()
    with log_path.open("w") as log_fh:
        log_fh.write(f"# cmd: {shlex.join(cmd)}\n")
        log_fh.write(f"# env overrides: {json.dumps(AFL_ENV)}\n")
        log_fh.write(f"# started: {datetime.now().isoformat()}\n")
        log_fh.flush()
        result = subprocess.run(
            cmd,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            env=env,
            cwd=_REPO_ROOT,
            check=False,
        )
        log_fh.write(f"\n# exit: {result.returncode}\n")
    duration = time.time() - start
    print(
        f"[{target} run{run_k}] afl exit={result.returncode} "
        f"wall={duration:.1f}s log={log_path.relative_to(out_root)}"
    )

    plot_data = run_dir / "default" / "plot_data"
    parsed_rows = 0
    if plot_data.exists():
        r = subprocess.run(
            [str(_VENV_PY), str(_PARSE_PLOT), str(plot_data), "--out", str(plot_csv)],
            capture_output=True,
            text=True,
            check=False,
        )
        if r.returncode == 0:
            with plot_csv.open() as fh:
                parsed_rows = max(0, sum(1 for _ in fh) - 1)
            print(f"[{target} run{run_k}] plot rows={parsed_rows}")
        else:
            print(f"[{target} run{run_k}] parse_plot_data failed: {r.stderr}")

    crash_count = 0
    summary_data: dict = {}
    crashes_dir = run_dir / "default" / "crashes"
    if crashes_dir.is_dir():
        r = subprocess.run(
            [
                str(_VENV_PY),
                str(_SUMMARIZE),
                "--target",
                target,
                str(run_dir),
                "--json-out",
                str(summary_json),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if r.returncode == 0 and summary_json.exists():
            summary_data = json.loads(summary_json.read_text())
            crash_count = summary_data.get("total_artifacts", 0)
            print(
                f"[{target} run{run_k}] crashes={crash_count} summary={summary_json.relative_to(out_root)}"
            )
        else:
            print(f"[{target} run{run_k}] summarize failed: {r.stderr}")

    return {
        "target": target,
        "run": run_k,
        "afl_exit": result.returncode,
        "wall_seconds": duration,
        "plot_rows": parsed_rows,
        "crashes": crash_count,
        "summary_counts": summary_data.get("counts", {}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument(
        "--target",
        required=True,
        choices=[*sorted(TARGETS), "all"],
        help="Target to benchmark, or 'all' for every target",
    )
    parser.add_argument(
        "--runs", type=int, default=3, help="Number of repeats per target"
    )
    parser.add_argument(
        "--seconds", type=int, default=900, help="Wall seconds per run (AFL -V)"
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output root (default: benchmarks/python_afl/runs/<UTC-timestamp>/)",
    )
    parser.add_argument(
        "--seeds",
        type=Path,
        default=None,
        help="Override seed dir (default: benchmarks/python_afl/seeds/<target>/)",
    )
    args = parser.parse_args()

    _preflight()

    out_root = args.out or (
        _REPO_ROOT
        / "benchmarks"
        / "python_afl"
        / "runs"
        / datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    )
    out_root.mkdir(parents=True, exist_ok=True)

    targets = sorted(TARGETS) if args.target == "all" else [args.target]

    meta = {
        "targets": targets,
        "runs_per_target": args.runs,
        "seconds_per_run": args.seconds,
        "started_utc": datetime.utcnow().isoformat() + "Z",
        "out_root": str(out_root),
    }
    (out_root / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")

    results: list[dict] = []
    for target in targets:
        if args.seeds is not None and args.target != "all":
            seeds_override = args.seeds
        else:
            seeds_override = None
        for k in range(args.runs):
            res = _run_single(target, k, args.seconds, out_root, seeds_override)
            results.append(res)
            (out_root / "results.jsonl").open("a").write(json.dumps(res) + "\n")

    print(f"\nall runs done. out_root={out_root}")
    print(f"total runs: {len(results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
