"""Run repeated fuzzer experiments across profiles and emit summary artifacts.

Outputs:
- results.csv: one row per run
- summary.md: aggregated per-profile + detailed per-run tables
"""

import argparse
import csv
import sqlite3
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from fuzzer.config import available_profiles


@dataclass
class RunRecord:
    profile: str
    repeat: int
    exit_code: int
    runtime_s: float
    run_dir: str
    executions: int
    execs_per_sec: float
    corpus_size: int
    interesting_seeds: int
    unique_crashes: int
    total_crashes: int
    line_coverage: int
    branch_coverage: int
    arc_coverage: int


def _parse_profiles(raw: str | None) -> list[str]:
    builtins = set(available_profiles())
    if raw is None:
        return sorted(builtins)

    profiles = [p.strip() for p in raw.split(",") if p.strip()]
    if not profiles:
        raise ValueError("--profiles must include at least one profile name")

    invalid = [p for p in profiles if p not in builtins]
    if invalid:
        available = ", ".join(sorted(builtins))
        raise ValueError(
            f"Unknown profile(s): {', '.join(invalid)}. Available: {available}"
        )
    return profiles


def _latest_run_dir(parent: Path) -> Path | None:
    candidates = [p for p in parent.iterdir() if p.is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _read_latest_metrics(db_path: Path) -> dict[str, int | float]:
    if not db_path.is_file():
        return {
            "executions": 0,
            "corpus_size": 0,
            "interesting_seed": 0,
            "unique_crashes": 0,
            "total_crashes": 0,
            "line_coverage": 0,
            "branch_coverage": 0,
            "arc_coverage": 0,
        }

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT
                executions,
                corpus_size,
                interesting_seed,
                unique_crashes,
                total_crashes,
                line_coverage,
                branch_coverage,
                total_edges
            FROM fuzzer_metrics
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return {
            "executions": 0,
            "corpus_size": 0,
            "interesting_seed": 0,
            "unique_crashes": 0,
            "total_crashes": 0,
            "line_coverage": 0,
            "branch_coverage": 0,
            "arc_coverage": 0,
        }

    return {
        "executions": int(row["executions"]),
        "corpus_size": int(row["corpus_size"]),
        "interesting_seed": int(row["interesting_seed"]),
        "unique_crashes": int(row["unique_crashes"]),
        "total_crashes": int(row["total_crashes"]),
        "line_coverage": int(row["line_coverage"]),
        "branch_coverage": int(row["branch_coverage"]),
        "arc_coverage": int(row["total_edges"]),
    }


def _build_cmd(profile: str, runs_dir: Path, time_limit: int) -> list[str]:
    return [
        "uv",
        "run",
        "python",
        "-m",
        "fuzzer",
        "--profile",
        profile,
        "--runs-dir",
        str(runs_dir),
        "--time-limit",
        str(time_limit),
        "--max-cycles",
        "-1",
    ]


def _compute_execs_per_sec(executions: int, runtime_s: float) -> float:
    if runtime_s <= 0:
        return 0.0
    return executions / runtime_s


def _write_csv(path: Path, rows: list[RunRecord]) -> None:
    fieldnames = [
        "profile",
        "repeat",
        "exit_code",
        "runtime_s",
        "run_dir",
        "executions",
        "execs_per_sec",
        "corpus_size",
        "interesting_seeds",
        "unique_crashes",
        "total_crashes",
        "line_coverage",
        "branch_coverage",
        "arc_coverage",
    ]

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "profile": row.profile,
                    "repeat": row.repeat,
                    "exit_code": row.exit_code,
                    "runtime_s": f"{row.runtime_s:.2f}",
                    "run_dir": row.run_dir,
                    "executions": row.executions,
                    "execs_per_sec": f"{row.execs_per_sec:.2f}",
                    "corpus_size": row.corpus_size,
                    "interesting_seeds": row.interesting_seeds,
                    "unique_crashes": row.unique_crashes,
                    "total_crashes": row.total_crashes,
                    "line_coverage": row.line_coverage,
                    "branch_coverage": row.branch_coverage,
                    "arc_coverage": row.arc_coverage,
                }
            )


def _aggregate_by_profile(rows: list[RunRecord]) -> list[dict[str, str]]:
    grouped: dict[str, list[RunRecord]] = {}
    for row in rows:
        grouped.setdefault(row.profile, []).append(row)

    output: list[dict[str, str]] = []
    for profile in sorted(grouped):
        grp = grouped[profile]
        count = len(grp)
        success = sum(1 for item in grp if item.exit_code == 0)
        output.append(
            {
                "profile": profile,
                "runs": str(count),
                "success": f"{success}/{count}",
                "avg_execs_per_sec": f"{sum(item.execs_per_sec for item in grp) / count:.2f}",
                "avg_executions": f"{sum(item.executions for item in grp) / count:.1f}",
                "avg_corpus": f"{sum(item.corpus_size for item in grp) / count:.1f}",
                "avg_unique_crashes": f"{sum(item.unique_crashes for item in grp) / count:.1f}",
                "avg_arcs": f"{sum(item.arc_coverage for item in grp) / count:.1f}",
            }
        )
    return output


def _markdown_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    out = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for row in rows:
        out.append("| " + " | ".join(row) + " |")
    return out


def _write_summary(
    path: Path,
    *,
    batch_id: str,
    time_limit: int,
    repeats: int,
    profiles: list[str],
    rows: list[RunRecord],
) -> None:
    aggregate = _aggregate_by_profile(rows)

    lines = [
        f"# Experiment Summary ({batch_id})",
        "",
        f"- Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"- Profiles: {', '.join(profiles)}",
        f"- Repeats per profile: {repeats}",
        f"- Time limit per run: {time_limit}s",
        "",
        "## Profile Aggregates",
        "",
    ]

    agg_headers = [
        "Profile",
        "Runs",
        "Success",
        "Avg Exec/s",
        "Avg Executions",
        "Avg Corpus",
        "Avg Unique Crashes",
        "Avg Arc Coverage",
    ]
    agg_rows = [
        [
            row["profile"],
            row["runs"],
            row["success"],
            row["avg_execs_per_sec"],
            row["avg_executions"],
            row["avg_corpus"],
            row["avg_unique_crashes"],
            row["avg_arcs"],
        ]
        for row in aggregate
    ]
    lines.extend(_markdown_table(agg_headers, agg_rows))

    lines.extend(["", "## Per-Run Results", ""])
    run_headers = [
        "Profile",
        "Repeat",
        "Exit",
        "Runtime(s)",
        "Exec/s",
        "Executions",
        "Corpus",
        "Unique Crashes",
        "Arcs",
        "Run Dir",
    ]
    run_rows = [
        [
            row.profile,
            str(row.repeat),
            str(row.exit_code),
            f"{row.runtime_s:.1f}",
            f"{row.execs_per_sec:.2f}",
            str(row.executions),
            str(row.corpus_size),
            str(row.unique_crashes),
            str(row.arc_coverage),
            row.run_dir,
        ]
        for row in rows
    ]
    lines.extend(_markdown_table(run_headers, run_rows))

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repeated fuzzer experiments")
    parser.add_argument(
        "--profiles",
        default=None,
        help="Comma-separated built-in profiles (default: all)",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=3,
        help="Number of runs per profile (default: 3)",
    )
    parser.add_argument(
        "--time-limit",
        type=int,
        default=180,
        help="Time limit in seconds per run (default: 180)",
    )
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=Path("runs"),
        help="Base runs directory passed to fuzzer (default: runs)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for experiment artifacts (default: runs/experiments/<timestamp>)",
    )
    args = parser.parse_args()

    if args.repeats < 1:
        raise ValueError("--repeats must be >= 1")
    if args.time_limit < 1:
        raise ValueError("--time-limit must be >= 1")

    profiles = _parse_profiles(args.profiles)

    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = args.output_dir or (args.runs_root / "experiments" / batch_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    records: list[RunRecord] = []
    total = len(profiles) * args.repeats
    current = 0

    for profile in profiles:
        for repeat in range(1, args.repeats + 1):
            current += 1
            print(
                f"[{current}/{total}] profile={profile} repeat={repeat} ...", flush=True
            )

            per_run_root = output_dir / "raw_runs" / profile / f"rep_{repeat}"
            per_run_root.mkdir(parents=True, exist_ok=True)
            cmd = _build_cmd(
                profile=profile, runs_dir=per_run_root, time_limit=args.time_limit
            )

            started = time.monotonic()
            completed = subprocess.run(cmd, cwd=str(Path.cwd()), check=False)
            wall_time = time.monotonic() - started

            run_dir = _latest_run_dir(per_run_root)
            db_path = run_dir / "results.db" if run_dir is not None else Path("")
            metrics = _read_latest_metrics(db_path)

            records.append(
                RunRecord(
                    profile=profile,
                    repeat=repeat,
                    exit_code=completed.returncode,
                    runtime_s=wall_time,
                    run_dir=str(run_dir) if run_dir is not None else "",
                    executions=int(metrics["executions"]),
                    execs_per_sec=_compute_execs_per_sec(
                        int(metrics["executions"]),
                        wall_time,
                    ),
                    corpus_size=int(metrics["corpus_size"]),
                    interesting_seeds=int(metrics["interesting_seed"]),
                    unique_crashes=int(metrics["unique_crashes"]),
                    total_crashes=int(metrics["total_crashes"]),
                    line_coverage=int(metrics["line_coverage"]),
                    branch_coverage=int(metrics["branch_coverage"]),
                    arc_coverage=int(metrics["arc_coverage"]),
                )
            )

    csv_path = output_dir / "results.csv"
    summary_path = output_dir / "summary.md"
    _write_csv(csv_path, records)
    _write_summary(
        summary_path,
        batch_id=batch_id,
        time_limit=args.time_limit,
        repeats=args.repeats,
        profiles=profiles,
        rows=records,
    )

    print(f"Wrote: {csv_path}")
    print(f"Wrote: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
