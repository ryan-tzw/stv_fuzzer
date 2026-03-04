"""Shared helpers and base class for coverage-based executors.

This module isolates the utility routines that are common across the three
implementations in ``executors.py`` so that the executor file itself can
focus solely on the public classes.  Keeping the helpers here also makes them
easier to reuse later (for example by a differential executor).
"""

import os
from pathlib import Path
from typing import List

_RUNNER_SCRIPT = Path(__file__).parent.parent / "_inprocess_runner.py"


def prepare_env(project_dir: Path) -> dict[str, str]:
    """Return an environment dict suitable for ``uv run``.

    The only adjustments we make are to set ``PYTHONPATH`` so the target
    project is importable and to remove ``VIRTUAL_ENV`` (``uv`` emits a
    warning otherwise).
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_dir)
    env.pop("VIRTUAL_ENV", None)
    return env


def uv_base_cmd(project_dir: Path) -> List[str]:
    """Base invocation used by all coverage executors.

    Additional arguments (runner script, coverage options, etc.) are
    appended by the caller.
    """
    return [
        "uv",
        "run",
        "--project",
        str(project_dir),
        "--with",
        "coverage",
        "python",
    ]


class CoverageExecutorBase:
    """Shared initialisation for the coverage-based executors.

    This class is *internal* to the executors package and is not exposed in
    ``__all__``.  It encapsulates the logic for resolving the project and
    script paths and normalising any script arguments.
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


__all__ = ["prepare_env", "uv_base_cmd", "CoverageExecutorBase", "_RUNNER_SCRIPT"]
