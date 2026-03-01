"""
Runs a harness script under coverage.py inside the target's uv environment.
"""

import argparse
import os
import subprocess
import tempfile
from pathlib import Path


class PythonCoverageExecutor:
    def __init__(
        self,
        project_dir: str | Path,
        script_path: str | Path,
        script_args: list[str] | None = None,
    ):
        self.project_dir = Path(project_dir).resolve()
        self.script_path = Path(script_path).resolve()
        self.script_args = [
            str(Path(a).resolve()) if Path(a).exists() else a
            for a in (script_args or [])
        ]

    def run(self, input_data: str | None = None) -> tuple[str, str, Path]:
        """
        Run the harness under coverage.py in the target's uv environment.
        If input_data is provided, it is passed to the harness via stdin.
        Returns (stdout, stderr, coverage_file_path).
        """
        fd, coverage_path = tempfile.mkstemp(suffix=".coverage")
        os.close(fd)
        coverage_file = Path(coverage_path)

        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.project_dir)
        env.pop("VIRTUAL_ENV", None)  # to remove warning

        result = subprocess.run(
            [
                "uv",
                "run",
                "--project",
                str(self.project_dir),
                "--with",
                "coverage",
                "python",
                "-m",
                "coverage",
                "run",
                "--branch",
                "--data-file",
                str(coverage_file),
                str(self.script_path),
                *self.script_args,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(self.project_dir),
            env=env,
            input=input_data,
        )

        return result.stdout, result.stderr, coverage_file


if __name__ == "__main__":
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
