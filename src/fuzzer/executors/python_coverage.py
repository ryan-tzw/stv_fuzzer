"""
Runs a harness script under coverage.py inside the target's uv environment.

Two executor variants are provided:

* PythonCoverageExecutor  – original implementation; writes a temp .coverage
  file that the observer reads back from disk.

* InProcessCoverageExecutor – leaner variant; uses a runner shim that runs
  coverage entirely in-memory (data_file=False) and returns coverage data as
  JSON over stdout.  No temporary files are written, removing the I/O
  bottleneck in the hot fuzzing loop.
"""

import argparse
import json
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


# --------------------------------------------------------------------------- #
#  In-process (no-file) variant                                             #
# --------------------------------------------------------------------------- #

_RUNNER_SCRIPT = Path(__file__).parent / "_inprocess_runner.py"


class InProcessCoverageExecutor:
    """
    Run a harness under coverage.py **without writing any .coverage file**.

    The executor delegates to ``_inprocess_runner.py``, a shim that starts
    coverage in-memory (``data_file=False``), runs the harness via
    ``runpy.run_path()``, then serialises the combined result as a single
    JSON line on stdout::

        {
            "stdout":    "<harness stdout>",
            "stderr":    "<harness stderr>",
            "exit_code": <int>,
            "coverage":  {"<abs_path>": {"lines": [...], "arcs": [...]}}
        }

    :meth:`run` returns ``(harness_stdout, harness_stderr, coverage_dict)``
    where *coverage_dict* is the parsed inner ``"coverage"`` mapping.
    This replaces the ``Path`` returned by :class:`PythonCoverageExecutor`
    so no observer clean-up step is needed.
    """

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

    def run(self, input_data: str | None = None) -> tuple[str, str, dict]:
        """
        Run the harness under in-memory coverage in the target's uv environment.

        If *input_data* is provided it is passed to the harness via stdin.
        Returns ``(harness_stdout, harness_stderr, coverage_dict)``.
        No temporary files are created or deleted.
        """
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.project_dir)
        env.pop("VIRTUAL_ENV", None)

        result = subprocess.run(
            [
                "uv",
                "run",
                "--project",
                str(self.project_dir),
                "--with",
                "coverage",
                "python",
                str(_RUNNER_SCRIPT),
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

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            # Runner itself crashed before producing JSON; surface raw output.
            return result.stdout, result.stderr, {}

        return (
            payload.get("stdout", ""),
            payload.get("stderr", ""),
            payload.get("coverage", {}),
        )


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
