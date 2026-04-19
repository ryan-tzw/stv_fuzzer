#!/usr/bin/env python3
"""Parse AFL ``plot_data`` into a normalized CSV for cross-baseline comparison.

AFL ``plot_data`` header (AFL++ 4.35c):

    # relative_time, cycles_done, cur_item, corpus_count, pending_total,
      pending_favs, map_size, saved_crashes, saved_hangs, max_depth,
      execs_per_sec, total_execs, edges_found, total_crashes, servers_count

The output CSV has the columns expected by ``aggregate_results.py``:

    elapsed_s, paths_total, edges_found, saved_crashes, execs_per_sec, total_execs
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

_OUT_FIELDS = [
    "elapsed_s",
    "paths_total",
    "edges_found",
    "saved_crashes",
    "execs_per_sec",
    "total_execs",
]


def parse(plot_data_path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    with plot_data_path.open() as fh:
        header: list[str] | None = None
        for line in fh:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                header = [c.strip() for c in line.lstrip("#").split(",")]
                continue
            if header is None:
                continue
            parts = [c.strip() for c in line.split(",")]
            if len(parts) != len(header):
                continue
            record = dict(zip(header, parts))
            try:
                rows.append(
                    {
                        "elapsed_s": float(record["relative_time"]),
                        "paths_total": float(record["corpus_count"]),
                        "edges_found": float(record["edges_found"]),
                        "saved_crashes": float(record["saved_crashes"]),
                        "execs_per_sec": float(record["execs_per_sec"]),
                        "total_execs": float(record["total_execs"]),
                    }
                )
            except KeyError:
                continue
            except ValueError:
                continue
    return rows


def write_csv(rows: list[dict[str, float]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=_OUT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("plot_data", type=Path, help="Path to AFL plot_data file")
    parser.add_argument(
        "--out", type=Path, required=True, help="Path to write the normalized CSV"
    )
    args = parser.parse_args()

    rows = parse(args.plot_data)
    write_csv(rows, args.out)
    print(f"wrote {len(rows)} rows -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
