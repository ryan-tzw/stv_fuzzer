#!/usr/bin/env python3
"""Aggregate python-afl benchmark runs into per-target CSVs + a summary report.

Reads the layout produced by ``run_benchmark.py``::

    <out_root>/
      <target>/
        run0.plot.csv
        run0.summary.json
        run1...
      results.jsonl
      meta.json

For each target, computes mean and stdev across the runs' final samples
of ``elapsed_s, paths_total, edges_found, saved_crashes, execs_per_sec,
total_execs``. Writes:

* ``<out_root>/results.csv`` — one row per (target, run) with final metrics
* ``<out_root>/results_mean.csv`` — one row per target with mean and stdev
* ``<out_root>/summary.md`` — readable report with crash counts by label
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path

_FINAL_METRICS = (
    "elapsed_s",
    "paths_total",
    "edges_found",
    "saved_crashes",
    "execs_per_sec",
    "total_execs",
)


def _read_last_row(plot_csv: Path) -> dict[str, float] | None:
    if not plot_csv.is_file():
        return None
    with plot_csv.open() as fh:
        reader = csv.DictReader(fh)
        last = None
        for row in reader:
            last = row
    if last is None:
        return None
    return {k: float(v) for k, v in last.items() if v != ""}


def _collect(out_root: Path) -> dict[str, list[dict]]:
    per_target: dict[str, list[dict]] = {}
    for target_dir in sorted(p for p in out_root.iterdir() if p.is_dir()):
        runs: list[dict] = []
        for plot_csv in sorted(target_dir.glob("run*.plot.csv")):
            run_idx = int(plot_csv.stem.split(".")[0].removeprefix("run"))
            final = _read_last_row(plot_csv) or {}
            summary_path = target_dir / f"run{run_idx}.summary.json"
            counts: dict[str, int] = {}
            total_crashes = 0
            if summary_path.is_file():
                data = json.loads(summary_path.read_text())
                counts = data.get("counts", {})
                total_crashes = data.get("total_artifacts", 0)
            runs.append(
                {
                    "run": run_idx,
                    "final": final,
                    "counts": counts,
                    "total_crashes": total_crashes,
                }
            )
        if runs:
            per_target[target_dir.name] = runs
    return per_target


def _write_results_csv(per_target: dict[str, list[dict]], out_path: Path) -> None:
    fields = ["target", "run", *_FINAL_METRICS, "unique_labels", "total_crashes"]
    with out_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for target, runs in per_target.items():
            for r in runs:
                row = {"target": target, "run": r["run"]}
                for m in _FINAL_METRICS:
                    row[m] = r["final"].get(m, "")
                row["unique_labels"] = len(r["counts"])
                row["total_crashes"] = r["total_crashes"]
                w.writerow(row)


def _write_mean_csv(per_target: dict[str, list[dict]], out_path: Path) -> None:
    fields = ["target", "runs"]
    for m in _FINAL_METRICS:
        fields += [f"{m}_mean", f"{m}_stdev"]
    fields += ["total_crashes_mean", "total_crashes_stdev", "unique_labels_mean"]
    with out_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for target, runs in per_target.items():
            row: dict = {"target": target, "runs": len(runs)}
            for m in _FINAL_METRICS:
                vals = [r["final"].get(m) for r in runs if m in r["final"]]
                if vals:
                    row[f"{m}_mean"] = round(statistics.fmean(vals), 3)
                    row[f"{m}_stdev"] = (
                        round(statistics.pstdev(vals), 3) if len(vals) > 1 else 0.0
                    )
                else:
                    row[f"{m}_mean"] = ""
                    row[f"{m}_stdev"] = ""
            crashes = [r["total_crashes"] for r in runs]
            labels = [len(r["counts"]) for r in runs]
            row["total_crashes_mean"] = round(statistics.fmean(crashes), 3)
            row["total_crashes_stdev"] = (
                round(statistics.pstdev(crashes), 3) if len(crashes) > 1 else 0.0
            )
            row["unique_labels_mean"] = round(statistics.fmean(labels), 3)
            w.writerow(row)


def _write_summary_md(
    per_target: dict[str, list[dict]], out_root: Path, out_path: Path
) -> None:
    lines: list[str] = ["# python-afl benchmark summary", ""]
    meta_path = out_root / "meta.json"
    if meta_path.is_file():
        meta = json.loads(meta_path.read_text())
        lines.append(
            f"- started: `{meta.get('started_utc', '?')}` — "
            f"seconds/run: `{meta.get('seconds_per_run', '?')}`, "
            f"runs/target: `{meta.get('runs_per_target', '?')}`"
        )
        lines.append(f"- out_root: `{meta.get('out_root', '?')}`")
    lines.append("")
    for target, runs in per_target.items():
        lines.append(f"## {target}")
        lines.append("")
        lines.append(
            f"- runs: {len(runs)}; total crashes across runs: "
            f"{sum(r['total_crashes'] for r in runs)}"
        )
        for m in _FINAL_METRICS:
            vals = [r["final"].get(m) for r in runs if m in r["final"]]
            if not vals:
                continue
            mean = statistics.fmean(vals)
            sd = statistics.pstdev(vals) if len(vals) > 1 else 0.0
            lines.append(f"- `{m}` mean±stdev: {mean:.2f} ± {sd:.2f}")
        all_counts: dict[str, int] = {}
        for r in runs:
            for lbl, n in r["counts"].items():
                all_counts[lbl] = all_counts.get(lbl, 0) + n
        if all_counts:
            lines.append("- crash labels (sum across runs):")
            for lbl, n in sorted(all_counts.items()):
                lines.append(f"  - {lbl}: {n}")
        lines.append("")
    out_path.write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("out_root", type=Path, help="run_benchmark output root")
    args = parser.parse_args()

    per_target = _collect(args.out_root)
    if not per_target:
        sys.exit(f"no run*.plot.csv files found under {args.out_root}")

    results_csv = args.out_root / "results.csv"
    mean_csv = args.out_root / "results_mean.csv"
    summary_md = args.out_root / "summary.md"
    _write_results_csv(per_target, results_csv)
    _write_mean_csv(per_target, mean_csv)
    _write_summary_md(per_target, args.out_root, summary_md)

    print(f"wrote {results_csv}")
    print(f"wrote {mean_csv}")
    print(f"wrote {summary_md}")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main())
