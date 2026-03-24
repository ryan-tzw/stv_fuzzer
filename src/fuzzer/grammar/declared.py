from __future__ import annotations

from pathlib import Path

from .loader import load_grammar_spec
from .parser import GrammarParser
from .service import GrammarService
from .spec import GrammarSpec
from .tree import DerivationNode


class DeclaredGrammarService(GrammarService):
    def __init__(self, spec: GrammarSpec) -> None:
        super().__init__(spec, max_depth=5)
        self._parser = GrammarParser(spec)

    @classmethod
    def from_file(cls, path: str | Path) -> "DeclaredGrammarService":
        return cls(load_grammar_spec(path))

    def parse(self, raw: str) -> DerivationNode | None:
        return self._parser.parse(raw)
