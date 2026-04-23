"""Markdown run report generation for fuzzing telemetry and crashes."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fuzzer.storage.database import FuzzerDatabase


CoverageLineKey = tuple[str, int]
CoverageArcKey = tuple[str, tuple[int, int]]


@dataclass(frozen=True)
class CoverageRatio:
    covered: int
    total: int
    percent: float


def generate_run_report(
    *,
    run_dir: Path,
    db: "FuzzerDatabase",
    project_dir: Path | None = None,
    seen_lines: frozenset[CoverageLineKey] | None = None,
    seen_branches: frozenset[CoverageArcKey] | None = None,
    seen_arcs: frozenset[CoverageArcKey] | None = None,
) -> Path:
    """Generate a markdown run report and return the output path."""
    report_dir = run_dir / "report"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "report.md"

    run_id = run_dir.name
    generated_at = datetime.now().isoformat(timespec="seconds")
    latest_metrics = db.get_latest_metrics_summary()
    crash_rows = db.get_crash_site_summary(limit=10)
    coverage_ratios = _coverage_ratios(
        project_dir=project_dir,
        seen_lines=seen_lines,
        seen_branches=seen_branches,
        seen_arcs=seen_arcs,
    )

    lines = [
        f"# Fuzzer Run Report ({run_id})",
        "",
        f"_Generated at: {generated_at}_",
        "",
        "## Summary",
        "",
        _summary_line("Executions", latest_metrics.get("executions", 0)),
        _summary_line(
            "Corpus Size", latest_metrics.get("corpus_size", db.get_corpus_size())
        ),
        _summary_line("Unique Crashes", latest_metrics.get("unique_crashes", 0)),
        _summary_line(
            "Line Coverage",
            _format_coverage_value(
                latest_metrics.get("line_coverage", 0),
                coverage_ratios.get("line"),
            ),
        ),
        _summary_line(
            "Branch Coverage",
            _format_coverage_value(
                latest_metrics.get("branch_coverage", 0),
                coverage_ratios.get("branch"),
            ),
        ),
        _summary_line(
            "Arc Coverage",
            _format_coverage_value(
                latest_metrics.get("arc_coverage", 0),
                coverage_ratios.get("arc"),
            ),
        ),
        _summary_line(
            "Exec/s",
            _format_execs_per_sec(latest_metrics.get("executions_per_sec", 0.0)),
        ),
        "",
        "## Graphs",
        "",
    ]
    lines.extend(_graph_section_lines(report_dir))
    lines.extend(
        [
            "",
            "## Crash Summary",
            "",
        ]
    )
    lines.extend(_crash_summary_lines(crash_rows))
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def _summary_line(label: str, value: object) -> str:
    if value is None:
        return f"- **{label}:** not available"
    return f"- **{label}:** {value}"


def _format_execs_per_sec(value: object) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.2f}"
    if isinstance(value, str):
        try:
            return f"{float(value):.2f}"
        except ValueError:
            return "0.00"
    try:
        return f"{float(str(value)):.2f}"
    except ValueError:
        return "0.00"


def _format_coverage_value(
    raw_count: object,
    ratio: CoverageRatio | None,
) -> object:
    if ratio is None:
        return raw_count
    return f"{ratio.covered}/{ratio.total} ({ratio.percent:.2f}%)"


def _coverage_ratios(
    *,
    project_dir: Path | None,
    seen_lines: frozenset[CoverageLineKey] | None,
    seen_branches: frozenset[CoverageArcKey] | None,
    seen_arcs: frozenset[CoverageArcKey] | None,
) -> dict[str, CoverageRatio]:
    if (
        project_dir is None
        or seen_lines is None
        or seen_branches is None
        or seen_arcs is None
    ):
        return {}

    from coverage.parser import PythonParser

    project_root = project_dir.resolve()
    files = _seen_files(
        seen_lines=seen_lines,
        seen_branches=seen_branches,
        seen_arcs=seen_arcs,
    )
    if not files:
        return {}

    lines_by_file = _index_lines(seen_lines)
    branches_by_file = _index_arcs(seen_branches)
    arcs_by_file = _index_arcs(seen_arcs)

    line_covered = 0
    line_total = 0
    branch_covered = 0
    branch_total = 0
    arc_covered = 0
    arc_total = 0

    for rel_path in sorted(files):
        file_path = (project_root / rel_path).resolve()
        try:
            file_path.relative_to(project_root)
        except ValueError:
            continue
        if not file_path.is_file():
            continue

        try:
            parser = PythonParser(filename=str(file_path))
            parser.parse_source()
        except Exception:
            continue

        static_lines = set(parser.statements)
        static_arcs = set(parser.arcs())
        exit_counts = parser.exit_counts()
        branch_source_lines = {line for line, exits in exit_counts.items() if exits > 1}
        static_branch_arcs = {
            arc for arc in static_arcs if arc[0] in branch_source_lines
        }

        line_total += len(static_lines)
        arc_total += len(static_arcs)
        branch_total += sum(exits for exits in exit_counts.values() if exits > 1)

        line_covered += len(lines_by_file.get(rel_path, set()) & static_lines)
        arc_covered += len(arcs_by_file.get(rel_path, set()) & static_arcs)
        branch_covered += len(
            branches_by_file.get(rel_path, set()) & static_branch_arcs
        )

    ratios: dict[str, CoverageRatio] = {}
    if line_total > 0:
        ratios["line"] = CoverageRatio(
            covered=line_covered,
            total=line_total,
            percent=(line_covered / line_total) * 100.0,
        )
    if branch_total > 0:
        ratios["branch"] = CoverageRatio(
            covered=branch_covered,
            total=branch_total,
            percent=(branch_covered / branch_total) * 100.0,
        )
    if arc_total > 0:
        ratios["arc"] = CoverageRatio(
            covered=arc_covered,
            total=arc_total,
            percent=(arc_covered / arc_total) * 100.0,
        )
    return ratios


def _seen_files(
    *,
    seen_lines: frozenset[CoverageLineKey],
    seen_branches: frozenset[CoverageArcKey],
    seen_arcs: frozenset[CoverageArcKey],
) -> set[str]:
    files = {file for file, _ in seen_lines}
    files.update(file for file, _ in seen_branches)
    files.update(file for file, _ in seen_arcs)
    return files


def _index_lines(
    seen_lines: frozenset[CoverageLineKey],
) -> dict[str, set[int]]:
    indexed: dict[str, set[int]] = defaultdict(set)
    for file, line in seen_lines:
        indexed[file].add(line)
    return indexed


def _index_arcs(
    seen_arcs: frozenset[CoverageArcKey],
) -> dict[str, set[tuple[int, int]]]:
    indexed: dict[str, set[tuple[int, int]]] = defaultdict(set)
    for file, arc in seen_arcs:
        indexed[file].add(arc)
    return indexed


def _graph_section_lines(report_dir: Path) -> list[str]:
    graph_specs = [
        ("Coverage Over Time", "coverage_over_time.png"),
        ("Unique Crashes Over Time", "unique_crashes_over_time.png"),
        ("Interesting Seeds Over Time", "interesting_seeds_over_time.png"),
    ]
    figure_dir = report_dir / "figures"
    lines: list[str] = []
    for title, filename in graph_specs:
        graph_path = figure_dir / filename
        rel = f"figures/{filename}"
        if graph_path.exists():
            lines.append(f"### {title}")
            lines.append(f"![{title}]({rel})")
        else:
            lines.append(f"- {title}: not available")
        lines.append("")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def _crash_summary_lines(rows: list[dict[str, object]]) -> list[str]:
    if not rows:
        return ["No crashes recorded."]

    lines = [
        "| Category | Exception | Location | Total Hits | Variants |",
        "|---|---|---|---:|---:|",
    ]
    for row in rows:
        category = str(row.get("bug_category", "unknown"))
        exc = str(row.get("exception_type", "unknown"))
        file = _trim_to_targets_prefix(str(row.get("file", "unknown")))
        line = row.get("line", -1)
        hits = row.get("total_hits", 0)
        variants = row.get("variants", 0)
        location = f"{file}:{line}"
        lines.append(f"| {category} | {exc} | {location} | {hits} | {variants} |")
    return lines


def _trim_to_targets_prefix(file_path: str) -> str:
    normalized = file_path.replace("\\", "/")
    marker = "targets/"
    idx = normalized.find(marker)
    if idx == -1:
        return file_path
    return normalized[idx:]
