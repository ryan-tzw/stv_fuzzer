from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .declared import DeclaredGrammarService
from .service import GrammarService

_SPEC_DIR = Path(__file__).with_name("specs")
_ALIASES = {
    "json": "json",
    "json-decoder": "json",
    "ipv4": "ipv4",
    "ipv4-parser": "ipv4",
    "ipv6": "ipv6",
    "ipv6-parser": "ipv6",
    "cidr": "cidrize",
    "cidrize": "cidrize",
    "cidrize-runner": "cidrize",
}


@lru_cache(maxsize=None)
def get_grammar(name: str) -> GrammarService | None:
    normalised = name.strip().lower()
    spec_name = _ALIASES.get(normalised)
    if spec_name is None:
        return None
    spec_path = _SPEC_DIR / f"{spec_name}.json"
    if spec_path.exists():
        return DeclaredGrammarService.from_file(spec_path)
    return None
