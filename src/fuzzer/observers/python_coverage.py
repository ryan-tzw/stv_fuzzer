"""
Observes coverage data produced by coverage.py and extracts
covered lines and branches for files within the target project.
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


class PythonCoverageObserver:
    def __init__(self, project_dir: str | Path):
        """
        project_dir: root of the target project — only files within this
        directory will be included in the coverage data.
        """
        self.project_dir = Path(project_dir).resolve()

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
            resolved = Path(file_path).resolve()
            try:
                resolved.relative_to(self.project_dir)
            except ValueError:
                continue  # outside project_dir — skip

            key = str(resolved.relative_to(self.project_dir))
            lines = data.lines(file_path)
            arcs = data.arcs(file_path)

            result.lines[key] = frozenset(lines) if lines else frozenset()
            result.branches[key] = frozenset(arcs) if arcs else frozenset()

        if cleanup:
            coverage_file.unlink(missing_ok=True)

        return result


if __name__ == "__main__":
    import argparse

    from fuzzer.executors.python_coverage import PythonCoverageExecutor

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
    stdout, stderr, coverage_file = executor.run()

    print("STDOUT:", stdout)
    if stderr:
        print("STDERR:", stderr)

    observer = PythonCoverageObserver(args.project_dir)
    data = observer.observe(coverage_file)

    print(f"\nCoverage ({data.total_lines()} lines, {data.total_branches()} branches):")
    for file, lines in data.lines.items():
        branches = data.branches.get(file, frozenset())
        sorted_lines = sorted(lines)
        sorted_branches = sorted(branches)
        print(f"  {file}: {len(lines)} lines, {len(branches)} branches")
        print(f"    lines:    {sorted_lines}")
        print(f"    branches: {sorted_branches}")
