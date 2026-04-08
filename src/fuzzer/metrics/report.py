"""Markdown run report generation for fuzzing telemetry and crashes."""

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fuzzer.storage.database import FuzzerDatabase


def generate_run_report(*, run_dir: Path, db: "FuzzerDatabase") -> Path:
    """Generate a markdown run report and return the output path."""
    report_dir = run_dir / "report"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "report.md"

    run_id = run_dir.name
    generated_at = datetime.now().isoformat(timespec="seconds")
    latest_metrics = db.get_latest_metrics_summary()
    crash_rows = db.get_crash_site_summary(limit=10)

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
        _summary_line("Line Coverage", latest_metrics.get("line_coverage", 0)),
        _summary_line("Branch Coverage", latest_metrics.get("branch_coverage", 0)),
        _summary_line("Arc Coverage", latest_metrics.get("arc_coverage", 0)),
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
