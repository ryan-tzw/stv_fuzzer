"""Parse structured crash metadata from target stderr/traceback output."""

import re
from dataclasses import dataclass
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
_EXCEPTION_LINE_RE = re.compile(
    r"^\s*(?P<exc>[A-Za-z_][A-Za-z0-9_\.]*)\s*:\s*(?P<msg>.*\S)?\s*$"
)
_EXCEPTION_CATEGORY_FALLBACK: dict[str, str] = {
    "jsondecodeerror": "bonus_untracked",
    "cidrizeerror": "bonus_untracked",
    "addrformaterror": "invalidity",
    "invalidcidrformaterror": "invalidity",
    "syntactic": "invalidity",
    "semantic": "validity",
    "validitybug": "validity",
    "invaliditybug": "invalidity",
    "performancebug": "performance",
    "functionalbug": "functional",
    "boundarybug": "boundary",
    "reliabilitybug": "reliability",
}
_WRAPPER_HINTS = (
    "pyi-",
    "failed to execute script",
    "pyinstaller",
)


@dataclass(frozen=True)
class _ExceptionCandidate:
    exc_type: str
    exc_message: str
    file: str
    line: int
    line_index: int


def parse_crash(stderr: str) -> ParsedCrash:
    """Parse target stderr into structured crash fields."""
    text = (stderr or "").strip()
    explicit = _extract_final_bug_tuple(text)
    if explicit is not None:
        return explicit

    traceback_text = _extract_traceback_text(text)
    canonical = _extract_canonical_exception(traceback_text)
    if canonical is None:
        exc_type, exc_msg, file, line = _extract_fallback_exception(traceback_text)
    else:
        exc_type = canonical.exc_type
        exc_msg = canonical.exc_message
        file = canonical.file
        line = canonical.line

    category = _extract_trigger_line_category(text) or "unknown"
    source = "trigger_line" if category != "unknown" else "traceback_fallback"
    if category == "unknown":
        fallback = _categorize_from_exception(exc_type, traceback_text)
        if fallback is not None:
            category = fallback
            source = "exception_fallback"

    return ParsedCrash(
        exception_type=exc_type.strip(),
        exception_message=exc_msg.strip(),
        file=file,
        line=line,
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
        bug_category=_normalize_category(match.group("category")),
        category_source="final_bug_count",
    )


def _extract_trigger_line_category(text: str) -> str | None:
    match = _TRIGGER_LINE_RE.search(text)
    if match is None:
        return None
    return _normalize_category(match.group(1))


def _extract_traceback_text(text: str) -> str:
    match = _TRACEBACK_BLOCK_RE.search(text)
    if match is not None:
        return match.group(1).strip()

    # Fallback: keep stderr text when no structured traceback block exists.
    return text.strip()


def _extract_canonical_exception(traceback_text: str) -> _ExceptionCandidate | None:
    candidates = _extract_exception_candidates(traceback_text)
    if not candidates:
        return None
    return max(candidates, key=_candidate_rank)


def _extract_exception_candidates(traceback_text: str) -> list[_ExceptionCandidate]:
    candidates: list[_ExceptionCandidate] = []
    current_file = "unknown"
    current_line = -1

    lines = traceback_text.splitlines()
    for index, raw_line in enumerate(lines):
        file_match = _FILE_LINE_RE.match(raw_line)
        if file_match is not None:
            current_file = file_match.group(1)
            current_line = int(file_match.group(2))
            continue

        match = _EXCEPTION_LINE_RE.match(raw_line)
        if match is None:
            continue
        exc_type = match.group("exc").strip()
        exc_msg = (match.group("msg") or "").strip()
        candidates.append(
            _ExceptionCandidate(
                exc_type=exc_type,
                exc_message=exc_msg,
                file=current_file,
                line=current_line,
                line_index=index,
            )
        )

    return candidates


def _candidate_rank(candidate: _ExceptionCandidate) -> tuple[int, int, int, int]:
    return (
        int(_is_known_exception(candidate.exc_type)),
        int(candidate.file != "unknown" and candidate.line != -1),
        int(not _looks_like_wrapper(candidate.exc_type, candidate.exc_message)),
        candidate.line_index,
    )


def _extract_fallback_exception(traceback_text: str) -> tuple[str, str, str, int]:
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
    if file_match is None:
        return exc_type, exc_msg, "unknown", -1

    return exc_type, exc_msg, file_match.group(1), int(file_match.group(2))


def _is_known_exception(exc_type: str) -> bool:
    stripped = exc_type.strip()
    if not stripped:
        return False
    simple = stripped.rsplit(".", 1)[-1]
    if simple.endswith("Bug"):
        return True
    key = re.sub(r"[^a-zA-Z0-9]", "", simple).lower()
    return key in _EXCEPTION_CATEGORY_FALLBACK


def _looks_like_wrapper(exc_type: str, exc_message: str) -> bool:
    lowered = f"{exc_type} {exc_message}".lower()
    return any(hint in lowered for hint in _WRAPPER_HINTS)


def _categorize_from_exception(exc_type: str, traceback_text: str) -> str | None:
    """
    Infer bug category from exception naming when explicit category markers are absent.
    """
    candidates: list[str] = []

    trimmed = exc_type.strip()
    if trimmed:
        candidates.append(trimmed)
        if "." in trimmed:
            candidates.append(trimmed.rsplit(".", 1)[-1])

    lines = traceback_text.splitlines()
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        head = line.split(":", 1)[0].strip()
        if head:
            candidates.append(head)
            if "." in head:
                candidates.append(head.rsplit(".", 1)[-1])
        break

    for name in candidates:
        key = re.sub(r"[^a-zA-Z0-9]", "", name).lower()
        category = _EXCEPTION_CATEGORY_FALLBACK.get(key)
        if category is not None:
            return category

    return None


def _normalize_category(category: str) -> str:
    key = re.sub(r"[^a-zA-Z0-9]", "", category).lower()
    return _EXCEPTION_CATEGORY_FALLBACK.get(key, key)
