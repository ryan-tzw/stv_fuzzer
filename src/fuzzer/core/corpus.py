"""
Corpus manager: loads seed inputs, tracks metadata, and persists via the database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from fuzzer.grammar import DerivationNode, GrammarService

if TYPE_CHECKING:
    from fuzzer.storage.database import FuzzerDatabase


@dataclass
class SeedMetadata:
    times_picked: int = 0
    times_fuzzed: int = 0


@dataclass
class SeedInput:
    raw_data: str
    tree: DerivationNode | None = None
    metadata: SeedMetadata = field(default_factory=SeedMetadata)


class CorpusManager:
    def __init__(
        self,
        corpus_dir: str | Path,
        db: FuzzerDatabase,
        grammar: GrammarService | None = None,
        generated_seed_count: int = 4,
    ):
        """
        corpus_dir: directory of initial seed files to load at startup (only used on first run).
        db:         database instance used to persist and reload seeds across runs.
        """
        self.corpus_dir = Path(corpus_dir).resolve()
        self._db = db
        self._grammar = grammar
        self._generated_seed_count = generated_seed_count
        self._seeds: list[SeedInput] = []

    def load(self) -> None:
        """
        Load seeds from the database if available, otherwise load from corpus_dir files
        and persist them to the database.
        """
        self._seeds = self._db.load_seeds()
        self._hydrate_trees()

        if not self._seeds:
            # First run — load from seed files and persist to DB
            paths = (
                sorted(self.corpus_dir.iterdir()) if self.corpus_dir.exists() else []
            )
            for path in paths:
                if path.is_file():
                    # Seed files are typically line-based text fixtures; trim the
                    # trailing line ending so grammar parsing sees the intended
                    # input rather than an editor-added newline.
                    raw_data = path.read_text(encoding="utf-8").rstrip("\r\n")
                    seed = SeedInput(
                        raw_data=raw_data,
                        tree=self._parse_tree(raw_data),
                    )
                    self._db.save_seed(seed)
                    self._seeds.append(seed)

        if not self._seeds and self._grammar is not None:
            for _ in range(self._generated_seed_count):
                tree = self._grammar.generate()
                seed = SeedInput(
                    raw_data=self._grammar.serialize(tree),
                    tree=tree,
                )
                self._db.save_seed(seed)
                self._seeds.append(seed)

        if not self._seeds:
            raise ValueError(
                f"No seed files found in corpus directory: {self.corpus_dir}"
            )

    def seeds(self) -> list[SeedInput]:
        """Return the current list of seeds."""
        return list(self._seeds)

    def add(self, raw_data: str, tree: DerivationNode | None = None) -> SeedInput:
        """
        Add an interesting input to the in-memory pool and persist it to the database.
        Returns the newly created SeedInput.
        """
        seed = SeedInput(raw_data=raw_data, tree=tree or self._parse_tree(raw_data))
        self._db.save_seed(seed)
        self._seeds.append(seed)
        return seed

    def record_picked(self, seed: SeedInput) -> None:
        """Increment the times_picked counter for a seed."""
        seed.metadata.times_picked += 1

    def record_fuzzed(self, seed: SeedInput) -> None:
        """Increment the times_fuzzed counter for a seed."""
        seed.metadata.times_fuzzed += 1

    def _parse_tree(self, raw_data: str) -> DerivationNode | None:
        if self._grammar is None:
            return None
        return self._grammar.parse(raw_data)

    def _hydrate_trees(self) -> None:
        if self._grammar is None:
            return
        for seed in self._seeds:
            if seed.tree is None:
                seed.tree = self._parse_tree(seed.raw_data)
