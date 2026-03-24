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
from fuzzer.observers.bug_category import parse_bug_category
from fuzzer.observers.input import ObservationInput


@dataclass
class CoverageData:
    lines: dict[str, frozenset[int]] = field(default_factory=dict)
    branches: dict[str, frozenset[tuple[int, int]]] = field(default_factory=dict)
    bug_category: str = "unknown"
    bug_category_source: str = "fallback"
    parsed_traceback: str = ""

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
    the persistent coverage execution pipeline.

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

    def observe(self, execution: ObservationInput) -> CoverageData:
        """Parse coverage payload from an ObservationInput."""
        coverage_dict = execution.result
        bug_info = parse_bug_category(execution.stderr)
        if not isinstance(coverage_dict, dict):
            return CoverageData(
                bug_category=bug_info.category,
                bug_category_source=bug_info.source,
                parsed_traceback=bug_info.traceback_text,
            )
        result = self.observe_payload(coverage_dict)
        result.bug_category = bug_info.category
        result.bug_category_source = bug_info.source
        result.parsed_traceback = bug_info.traceback_text
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

            result.lines[key] = frozenset(lines)
            result.branches[key] = frozenset(
                (arc[0], arc[1]) for arc in arcs if len(arc) == 2
            )

        return result
