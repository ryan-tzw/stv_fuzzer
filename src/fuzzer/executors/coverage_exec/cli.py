"""Command-line front end for the coverage executors (for testing only)."""

import argparse

from .file_executor import PythonCoverageExecutor


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a harness script with coverage.py"
    )
    parser.add_argument("project_dir", help="Path to the target's uv project directory")
    parser.add_argument("script_path", help="Path to the harness script to run")
    parser.add_argument(
        "script_args",
        nargs=argparse.REMAINDER,
        help="Arguments to pass to the harness",
    )
    args = parser.parse_args()

    executor = PythonCoverageExecutor(
        args.project_dir, args.script_path, args.script_args
    )
    run_result = executor.run()

    print("STDOUT:", run_result.stdout)
    print("STDERR:", run_result.stderr)
    print("Exit code:", run_result.exit_code)
    print("Coverage file:", run_result.result)


if __name__ == "__main__":
    main()
