from __future__ import annotations

import random

from .spec import GrammarSpec, Literal, SymbolRef
from .tree import DerivationNode, literal


class GrammarGenerator:
    def __init__(self, spec: GrammarSpec, max_depth: int = 5) -> None:
        self._spec = spec
        self._max_depth = max_depth

    def generate(self) -> DerivationNode:
        return self.generate_symbol(self._spec.start_symbol)

    def generate_symbol(self, symbol: str, depth: int = 0) -> DerivationNode:
        if self._spec.is_terminal(symbol):
            return DerivationNode(
                symbol=symbol,
                text=self._spec.terminal_generators[symbol](),
            )

        productions = self._spec.productions_for(symbol)
        choices = list(range(len(productions)))
        if depth >= self._max_depth:
            depth_limited = self._spec.depth_limited_choices.get(symbol)
            if depth_limited:
                choices = list(depth_limited)

        production_index = random.choice(choices)
        production = productions[production_index]
        children: list[DerivationNode] = []

        for item in production.items:
            if isinstance(item, Literal):
                children.append(literal(item.text))
            elif isinstance(item, SymbolRef):
                children.append(self.generate_symbol(item.name, depth + 1))
            else:  # pragma: no cover - defensive only
                raise TypeError(f"Unsupported grammar item: {item!r}")

        return DerivationNode(
            symbol=symbol,
            production_index=production_index,
            children=children,
        )
