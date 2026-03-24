from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

LITERAL_SYMBOL = "__literal__"


@dataclass
class DerivationNode:
    symbol: str
    production_index: int | None = None
    children: list["DerivationNode"] = field(default_factory=list)
    text: str | None = None

    def clone(self) -> "DerivationNode":
        return DerivationNode(
            symbol=self.symbol,
            production_index=self.production_index,
            children=[child.clone() for child in self.children],
            text=self.text,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "production_index": self.production_index,
            "children": [child.to_dict() for child in self.children],
            "text": self.text,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DerivationNode":
        return cls(
            symbol=payload["symbol"],
            production_index=payload.get("production_index"),
            children=[cls.from_dict(child) for child in payload.get("children", [])],
            text=payload.get("text"),
        )


def literal(text: str) -> DerivationNode:
    return DerivationNode(symbol=LITERAL_SYMBOL, text=text)
