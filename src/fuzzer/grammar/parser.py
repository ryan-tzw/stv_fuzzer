from __future__ import annotations

import re

from .spec import GrammarSpec, Literal, SymbolRef
from .tree import DerivationNode, literal


class GrammarParser:
    def __init__(self, spec: GrammarSpec) -> None:
        self._spec = spec
        self._token_patterns = {
            symbol: re.compile(pattern)
            for symbol, pattern in spec.token_patterns.items()
        }
        self._skip_pattern = (
            re.compile(spec.skip_pattern) if spec.skip_pattern else None
        )

    def parse(self, raw: str) -> DerivationNode | None:
        node, position = self._parse_symbol(self._spec.start_symbol, raw, 0)
        if node is None:
            return None
        position = self._skip(raw, position)
        if position != len(raw):
            return None
        return node

    def _parse_symbol(
        self, symbol: str, raw: str, position: int
    ) -> tuple[DerivationNode | None, int]:
        position = self._skip(raw, position)

        if self._spec.is_terminal(symbol):
            pattern = self._token_patterns.get(symbol)
            if pattern is None:
                return None, position
            match = pattern.match(raw, position)
            if match is None:
                return None, position
            return DerivationNode(symbol=symbol, text=match.group(0)), match.end()

        for production_index, production in enumerate(
            self._spec.productions_for(symbol)
        ):
            current = position
            children: list[DerivationNode] = []
            success = True

            for item in production.items:
                current = self._skip(raw, current)

                if isinstance(item, Literal):
                    if raw.startswith(item.text, current):
                        children.append(literal(item.text))
                        current += len(item.text)
                    else:
                        success = False
                        break
                elif isinstance(item, SymbolRef):
                    child, current = self._parse_symbol(item.name, raw, current)
                    if child is None:
                        success = False
                        break
                    children.append(child)
                else:  # pragma: no cover - defensive only
                    raise TypeError(f"Unsupported grammar item: {item!r}")

            if success:
                return (
                    DerivationNode(
                        symbol=symbol,
                        production_index=production_index,
                        children=children,
                    ),
                    current,
                )

        return None, position

    def _skip(self, raw: str, position: int) -> int:
        if self._skip_pattern is None:
            return position
        match = self._skip_pattern.match(raw, position)
        if match is None:
            return position
        return match.end()
