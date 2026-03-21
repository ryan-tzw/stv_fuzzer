"""
Observes coverage data produced by coverage.py and extracts
covered lines and branches for files within the target project.

Two observer variants are provided:

* PythonCoverageObserver     – reads a ``.coverage`` file from disk.
* InProcessCoverageObserver  – parses the in-memory coverage dict returned
  by :class:`~fuzzer.executors.coverage_exec.python.InProcessCoverageExecutor`.
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CoverageData:
    lines: dict[str, frozenset[int]] = field(default_factory=dict)
    branches: dict[str, frozenset[tuple[int, int]]] = field(default_factory=dict)

    def total_lines(self) -> int:
        return sum(len(v) for v in self.lines.values())

    def total_branches(self) -> int:
        return sum(len(v) for v in self.branches.values())


class _ProjectScopedCoverageObserver:
    def __init__(self, project_dir: str | Path):
        self.project_dir = Path(project_dir).resolve()

    def _scoped_key(self, file_path: str | Path) -> str | None:
        resolved = Path(file_path).resolve()
        try:
            return str(resolved.relative_to(self.project_dir))
        except ValueError:
            return None


class PythonCoverageObserver(_ProjectScopedCoverageObserver):
    """
    Read a ``.coverage`` file from disk and produce project-scoped coverage.
    """

    def observe(self, coverage_file: Path, cleanup: bool = True) -> CoverageData:
        """
        Read the .coverage file and return CoverageData scoped to the target project.
        If cleanup is True (default), the coverage file is deleted after reading.
        """
        from coverage import Coverage

        cov = Coverage(data_file=str(coverage_file))
        cov.load()

        data = cov.get_data()
        result = CoverageData()

        for file_path in data.measured_files():
            key = self._scoped_key(file_path)
            if key is None:
                continue  # outside project_dir — skip

            lines = data.lines(file_path)
            arcs = data.arcs(file_path)

            result.lines[key] = frozenset(lines) if lines else frozenset()
            result.branches[key] = frozenset(arcs) if arcs else frozenset()

        if cleanup:
            coverage_file.unlink(missing_ok=True)

        return result


# --------------------------------------------------------------------------- #
#  In-process (no-file) variant                                             #
# --------------------------------------------------------------------------- #


class InProcessCoverageObserver(_ProjectScopedCoverageObserver):
    """
    Derive :class:`CoverageData` from the coverage dict produced by
    :class:`~fuzzer.executors.coverage.python.InProcessCoverageExecutor`.

    The dict has the shape::

        {
            "<abs_file_path>": {
                "lines": [int, ...],
                "arcs":  [[int, int], ...]
            },
            ...
        }

    Results are scoped to files that live inside *project_dir*, matching
    the behaviour of :class:`PythonCoverageObserver`.
    """

    def observe(self, coverage_dict: dict) -> CoverageData:
        """
        Parse *coverage_dict* and return coverage scoped to *project_dir*.
        """
        result = CoverageData()

        for file_path, file_data in coverage_dict.items():
            key = self._scoped_key(file_path)
            if key is None:
                continue  # outside project_dir — skip

            lines = file_data.get("lines") or []
            arcs = file_data.get("arcs") or []

            result.lines[key] = frozenset(lines)
            result.branches[key] = frozenset(tuple(a) for a in arcs)

        return result


if __name__ == "__main__":
    import argparse

    from fuzzer.executors.coverage_exec.python import PythonCoverageExecutor

    parser = argparse.ArgumentParser(description="Run a harness and observe coverage")
    parser.add_argument("project_dir", help="Path to the target's uv project directory")
    parser.add_argument("script_path", help="Path to the harness script to run")
    parser.add_argument(
        "script_args", nargs=argparse.REMAINDER, help="Arguments to pass to the harness"
    )
    args = parser.parse_args()

    executor = PythonCoverageExecutor(
        args.project_dir, args.script_path, args.script_args
    )
    run_result = executor.run()

    print("STDOUT:", run_result.stdout)
    print("Exit code:", run_result.exit_code)
    if run_result.stderr:
        print("STDERR:", run_result.stderr)

    observer = PythonCoverageObserver(args.project_dir)
    data = observer.observe(run_result.result)

    print(f"\nCoverage ({data.total_lines()} lines, {data.total_branches()} branches):")
    for file, lines in data.lines.items():
        branches = data.branches.get(file, frozenset())
        sorted_lines = sorted(lines)
        sorted_branches = sorted(branches)
        print(f"  {file}: {len(lines)} lines, {len(branches)} branches")
        print(f"    lines:    {sorted_lines}")
        print(f"    branches: {sorted_branches}")
