"""Thin loader for Lark grammar files."""

from pathlib import Path

from lark import Lark

_GRAMMARS_DIR = Path(__file__).resolve().parent / "grammars"


def load_parser(
    name_or_path: str | Path,
    *,
    start: str = "start",
    parser: str = "earley",
) -> Lark:
    """Load and return a configured Lark parser."""
    grammar_path = _resolve_grammar_path(name_or_path)

    if grammar_path.suffix != ".lark":
        raise ValueError(f"Grammar file must use .lark extension: {grammar_path}")
    if not grammar_path.exists() or not grammar_path.is_file():
        raise ValueError(f"Grammar file not found: {grammar_path}")

    return Lark.open(
        str(grammar_path),
        parser=parser,
        start=start,
        keep_all_tokens=True,
    )


def _resolve_grammar_path(name_or_path: str | Path) -> Path:
    candidate = Path(name_or_path)

    if candidate.exists():
        return candidate.resolve()

    candidate_str = str(name_or_path)
    if candidate_str.endswith(".lark"):
        return candidate.resolve()

    return (_GRAMMARS_DIR / f"{candidate_str}.lark").resolve()
