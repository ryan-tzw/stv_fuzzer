"""Smoke-check for DifferentialExecutor composition.

This utility composes:
- BinaryExecutor (blackbox target)
- PersistentCoverageExecutor (whitebox reference)

It runs one input through both and prints the raw result summary.
"""

import argparse
from pathlib import Path
from typing import Any

from fuzzer.executors import (
    BinaryExecutor,
    DifferentialExecutor,
    PersistentCoverageExecutor,
)


def _coverage_summary(payload: Any) -> tuple[int, int, int]:
    if not isinstance(payload, dict):
        return (0, 0, 0)

    file_count = len(payload)
    line_count = 0
    arc_count = 0
    for entry in payload.values():
        if not isinstance(entry, dict):
            continue
        lines = entry.get("lines") or []
        arcs = entry.get("arcs") or []
        line_count += len(lines)
        arc_count += len(arcs)

    return (file_count, line_count, arc_count)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one DifferentialExecutor smoke test"
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Input string passed to both executors",
    )

    parser.add_argument(
        "--blackbox-binary",
        type=Path,
        required=True,
        help="Path to blackbox binary executable",
    )
    parser.add_argument(
        "--blackbox-input-flag",
        default="--ipstr",
        help="CLI flag used to pass blackbox input (default: --ipstr)",
    )
    parser.add_argument(
        "--blackbox-arg",
        action="append",
        default=[],
        help="Static arg for blackbox binary (repeatable)",
    )
    parser.add_argument(
        "--blackbox-timeout",
        type=float,
        default=5.0,
        help="Blackbox run timeout in seconds (default: 5.0)",
    )

    parser.add_argument(
        "--whitebox-project-dir",
        type=Path,
        required=True,
        help="Path to whitebox uv project directory",
    )
    parser.add_argument(
        "--whitebox-harness-path",
        type=Path,
        required=True,
        help="Path to whitebox harness script",
    )
    parser.add_argument(
        "--whitebox-arg",
        action="append",
        default=[],
        help="Extra arg passed to whitebox harness (repeatable)",
    )

    args = parser.parse_args()

    blackbox = BinaryExecutor(
        binary_path=args.blackbox_binary.resolve(),
        input_flag=args.blackbox_input_flag,
        static_args=list(args.blackbox_arg),
        timeout=args.blackbox_timeout,
    )
    whitebox = PersistentCoverageExecutor(
        project_dir=args.whitebox_project_dir.resolve(),
        script_path=args.whitebox_harness_path.resolve(),
        script_args=list(args.whitebox_arg),
    )

    executor = DifferentialExecutor(blackbox=blackbox, whitebox=whitebox)

    with executor:
        result = executor.run(args.input)

    differential = result.result

    print("=== Differential Run ===")
    print(f"top.exit_code: {result.exit_code}")

    print("--- Blackbox ---")
    print(f"blackbox.exit_code: {differential.blackbox.exit_code}")
    print(f"blackbox.stdout_len: {len(differential.blackbox.stdout)}")
    print(f"blackbox.stderr_len: {len(differential.blackbox.stderr)}")

    print("--- Whitebox ---")
    print(f"whitebox.exit_code: {differential.whitebox.exit_code}")
    print(f"whitebox.stdout_len: {len(differential.whitebox.stdout)}")
    print(f"whitebox.stderr_len: {len(differential.whitebox.stderr)}")

    file_count, line_count, arc_count = _coverage_summary(differential.whitebox.result)
    print(f"whitebox.coverage_files: {file_count}")
    print(f"whitebox.covered_lines: {line_count}")
    print(f"whitebox.covered_arcs: {arc_count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
