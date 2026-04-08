"""
Observes coverage data produced by coverage.py and extracts
covered lines and branches for files within the target project.

Two observer variants are provided:

* PythonCoverageObserver     – reads a ``.coverage`` file from disk.
* InProcessCoverageObserver  – parses the in-memory coverage dict returned
    by the in-process runner used by the persistent coverage executor.
"""

from dataclasses import dataclass, field
from pathlib import Path

from fuzzer.executors.coverage_exec.types import CoveragePayload
from fuzzer.observers.bug_category import parse_crash
from fuzzer.observers.input import ObservationInput, ParsedCrash


@dataclass
class CoverageData:
    lines: dict[str, frozenset[int]] = field(default_factory=dict)
    # NOTE: branches stores arcs for compatibility with existing feedback logic.
    branches: dict[str, frozenset[tuple[int, int]]] = field(default_factory=dict)
    # Decision-point source lines (from coverage.py branch_stats) used to
    # derive true branch-exit counts from arc observations.
    branch_decision_lines: dict[str, frozenset[int]] = field(default_factory=dict)
    parsed_crash: ParsedCrash | None = None

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
            branch_stats = cov.branch_stats(file_path)

            result.lines[key] = frozenset(lines) if lines else frozenset()
            result.branches[key] = frozenset(arcs) if arcs else frozenset()
            result.branch_decision_lines[key] = frozenset(branch_stats.keys())

        if cleanup:
            coverage_file.unlink(missing_ok=True)

        return result


# --------------------------------------------------------------------------- #
#  In-process (no-file) variant                                             #
# --------------------------------------------------------------------------- #


class InProcessCoverageObserver(_ProjectScopedCoverageObserver):
    """
    Derive :class:`CoverageData` from the coverage dict produced by
    the persistent coverage execution pipeline.

    The dict has the shape::

        {
            "<abs_file_path>": {
                "lines": [int, ...],
                "arcs":  [[int, int], ...],
                "branch_stats": [
                    {"line": int, "exits": int, "taken": int},
                    ...
                ]  # optional
            },
            ...
        }

    Results are scoped to files that live inside *project_dir*, matching
    the behaviour of :class:`PythonCoverageObserver`.
    """

    def observe(self, execution: ObservationInput) -> CoverageData:
        """Parse coverage payload from an ObservationInput."""
        coverage_dict = execution.result
        parsed_crash = parse_crash(execution.stderr)
        if not isinstance(coverage_dict, dict):
            return CoverageData(parsed_crash=parsed_crash)
        result = self.observe_payload(coverage_dict)
        result.parsed_crash = parsed_crash
        return result

    def observe_payload(self, coverage_dict: CoveragePayload) -> CoverageData:
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
            branch_stats = file_data.get("branch_stats") or []

            result.lines[key] = frozenset(lines)
            result.branches[key] = frozenset(
                (arc[0], arc[1]) for arc in arcs if len(arc) == 2
            )
            result.branch_decision_lines[key] = frozenset(
                int(entry["line"])
                for entry in branch_stats
                if isinstance(entry, dict) and "line" in entry
            )

        return result
