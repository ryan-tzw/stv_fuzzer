"""Parse target-reported bug category details from stderr/traceback text."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class BugCategoryInfo:
    category: str
    source: str
    traceback_text: str


_FINAL_BUG_COUNT_RE = re.compile(
    r"Final bug count:\s*defaultdict\([^\{]*\{\(\s*'([^']+)'\s*,",
    flags=re.IGNORECASE | re.DOTALL,
)
_TRIGGER_LINE_RE = re.compile(
    r"An\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+bug has been triggered",
    flags=re.IGNORECASE,
)
_TRACEBACK_BLOCK_RE = re.compile(
    r"TRACEBACK\s*=+\s*(Traceback \(most recent call last\):.*?)(?:\n=+|\Z)",
    flags=re.IGNORECASE | re.DOTALL,
)


def parse_bug_category(stderr: str) -> BugCategoryInfo:
    text = stderr or ""

    explicit = _extract_final_bug_count_category(text)
    if explicit is not None:
        return BugCategoryInfo(
            category=explicit,
            source="final_bug_count",
            traceback_text=_extract_traceback_text(text),
        )

    triggered = _extract_trigger_line_category(text)
    if triggered is not None:
        return BugCategoryInfo(
            category=triggered,
            source="trigger_line",
            traceback_text=_extract_traceback_text(text),
        )

    return BugCategoryInfo(
        category="unknown",
        source="fallback",
        traceback_text=_extract_traceback_text(text),
    )


def _extract_final_bug_count_category(text: str) -> str | None:
    match = _FINAL_BUG_COUNT_RE.search(text)
    if match is None:
        return None
    return match.group(1).strip().lower()


def _extract_trigger_line_category(text: str) -> str | None:
    match = _TRIGGER_LINE_RE.search(text)
    if match is None:
        return None
    return match.group(1).strip().lower()


def _extract_traceback_text(text: str) -> str:
    match = _TRACEBACK_BLOCK_RE.search(text)
    if match is not None:
        return match.group(1).strip()

    # Fallback: keep stderr text when no structured traceback block exists.
    return text.strip()
