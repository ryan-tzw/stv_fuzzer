from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class Literal:
    text: str


@dataclass(frozen=True)
class SymbolRef:
    name: str


GrammarItem = Literal | SymbolRef


@dataclass(frozen=True)
class Production:
    items: tuple[GrammarItem, ...] = ()


@dataclass
class GrammarSpec:
    name: str
    start_symbol: str
    productions: dict[str, tuple[Production, ...]]
    terminal_generators: dict[str, Callable[[], str]] = field(default_factory=dict)
    token_patterns: dict[str, str] = field(default_factory=dict)
    depth_limited_choices: dict[str, tuple[int, ...]] = field(default_factory=dict)
    skip_pattern: str | None = None

    def productions_for(self, symbol: str) -> tuple[Production, ...]:
        productions = self.productions.get(symbol)
        if productions is None:
            raise KeyError(f"Unknown grammar symbol: {symbol}")
        return productions

    def is_terminal(self, symbol: str) -> bool:
        return symbol in self.terminal_generators or symbol in self.token_patterns

    def is_nonterminal(self, symbol: str) -> bool:
        return symbol in self.productions


def lit(text: str) -> Literal:
    return Literal(text=text)


def ref(name: str) -> SymbolRef:
    return SymbolRef(name=name)
