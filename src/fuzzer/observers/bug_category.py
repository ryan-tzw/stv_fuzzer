"""Parse structured crash metadata from target stderr/traceback output."""

import re
from fuzzer.observers.input import ParsedCrash


_FINAL_BUG_COUNT_RE = re.compile(
    r"Final bug count:\s*defaultdict\([^\{]*\{\(\s*"
    r"'(?P<category>[^']+)'\s*,\s*"
    r"<class '(?P<exc_path>[^']+)'>\s*,\s*"
    r"'(?P<message>(?:\\'|[^'])*)'\s*,\s*"
    r"'(?P<file>(?:\\'|[^'])*)'\s*,\s*"
    r"(?P<line>\d+)\s*\)",
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
_FILE_LINE_RE = re.compile(r'\s*File "(.+)", line (\d+)')


def parse_crash(stderr: str) -> ParsedCrash:
    """Parse target stderr into structured crash fields."""
    text = (stderr or "").strip()
    explicit = _extract_final_bug_tuple(text)
    if explicit is not None:
        return explicit

    traceback_text = _extract_traceback_text(text)

    lines = traceback_text.splitlines()
    last_line = lines[-1].strip() if lines else ""
    if ":" in last_line:
        exc_type, exc_msg = last_line.split(":", 1)
    else:
        exc_type, exc_msg = last_line, ""

    file_match = None
    for line in reversed(lines):
        file_match = _FILE_LINE_RE.match(line)
        if file_match:
            break

    category = _extract_trigger_line_category(text) or "unknown"
    source = "trigger_line" if category != "unknown" else "traceback_fallback"

    return ParsedCrash(
        exception_type=exc_type.strip(),
        exception_message=exc_msg.strip(),
        file=file_match.group(1) if file_match else "unknown",
        line=int(file_match.group(2)) if file_match else -1,
        traceback=traceback_text,
        bug_category=category,
        category_source=source,
    )


def _extract_final_bug_tuple(text: str) -> ParsedCrash | None:
    match = _FINAL_BUG_COUNT_RE.search(text)
    if match is None:
        return None

    exc_path = match.group("exc_path").strip()
    return ParsedCrash(
        exception_type=exc_path.rsplit(".", 1)[-1],
        exception_message=match.group("message").replace("\\'", "'").strip(),
        file=match.group("file").replace("\\'", "'").strip(),
        line=int(match.group("line")),
        traceback=_extract_traceback_text(text),
        bug_category=match.group("category").strip().lower(),
        category_source="final_bug_count",
    )


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
