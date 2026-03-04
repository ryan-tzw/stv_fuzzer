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
    stdout, stderr, coverage_file = executor.run()

    print("STDOUT:", stdout)
    print("STDERR:", stderr)
    print("Coverage file:", coverage_file)


if __name__ == "__main__":
    main()
