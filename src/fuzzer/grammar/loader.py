from __future__ import annotations

import json
from pathlib import Path

from .spec import GrammarItem, GrammarSpec, Production, lit, ref
from .terminals import resolve_terminal_generator


def load_grammar_spec(path: str | Path) -> GrammarSpec:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))

    productions = {
        symbol: tuple(
            Production(tuple(_load_item(item) for item in production))
            for production in alternatives
        )
        for symbol, alternatives in payload["productions"].items()
    }

    tokens = payload.get("tokens", {})
    return GrammarSpec(
        name=payload["name"],
        start_symbol=payload["start_symbol"],
        productions=productions,
        terminal_generators={
            name: resolve_terminal_generator(token["generator"])
            for name, token in tokens.items()
        },
        token_patterns={name: token["pattern"] for name, token in tokens.items()},
        depth_limited_choices={
            symbol: tuple(choices)
            for symbol, choices in payload.get("depth_limited_choices", {}).items()
        },
        skip_pattern=payload.get("skip_pattern"),
    )


def _load_item(item: dict[str, str]) -> GrammarItem:
    if "literal" in item:
        return lit(item["literal"])
    if "symbol" in item:
        return ref(item["symbol"])
    raise ValueError(f"Unsupported grammar item: {item!r}")
