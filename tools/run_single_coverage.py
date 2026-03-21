"""Run a harness once under coverage and print a compact summary.

This is a developer utility script. It is intentionally outside the runtime
`fuzzer` package so production architecture stays focused on persistent mode.
"""

import argparse
import json
import os
import subprocess
from pathlib import Path


def _build_cmd(
    project_dir: Path, harness_path: Path, harness_args: list[str]
) -> list[str]:
    runner = Path("src/fuzzer/executors/_inprocess_runner.py").resolve()
    return [
        "uv",
        "run",
        "--project",
        str(project_dir),
        "--with",
        "coverage",
        "python",
        str(runner),
        str(harness_path),
        *harness_args,
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one harness execution with coverage"
    )
    parser.add_argument("project_dir", type=Path, help="Target uv project directory")
    parser.add_argument("harness_path", type=Path, help="Path to harness script")
    parser.add_argument(
        "--input",
        default="",
        help="Input string to send on stdin (default: empty)",
    )
    args, harness_args = parser.parse_known_args()

    cmd = _build_cmd(
        project_dir=args.project_dir.resolve(),
        harness_path=args.harness_path.resolve(),
        harness_args=harness_args,
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = str(args.project_dir.resolve())
    env.pop("VIRTUAL_ENV", None)

    result = subprocess.run(
        cmd,
        input=args.input,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(Path.cwd()),
        env=env,
    )

    if result.returncode != 0:
        print("Runner invocation failed")
        if result.stderr:
            print(result.stderr)
        return result.returncode

    payload = json.loads(result.stdout)
    coverage = payload.get("coverage", {})
    line_count = sum(len(file_data.get("lines", [])) for file_data in coverage.values())
    branch_count = sum(
        len(file_data.get("arcs", [])) for file_data in coverage.values()
    )

    print("Exit code:", payload.get("exit_code", -1))
    print("STDOUT:")
    print(payload.get("stdout", ""))
    stderr = payload.get("stderr", "")
    if stderr:
        print("STDERR:")
        print(stderr)
    print("Coverage files:", len(coverage))
    print("Covered lines:", line_count)
    print("Covered arcs:", branch_count)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
