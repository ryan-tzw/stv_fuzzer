"""
Corpus manager: loads seed inputs, tracks metadata, and persists via the database.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from ..grammars.generator.generator import GrammarSeedGenerator

if TYPE_CHECKING:
    from fuzzer.storage.database import FuzzerDatabase


@dataclass
class SeedMetadata:
    times_picked: int = 0
    times_fuzzed: int = 0


@dataclass
class SeedInput:
    data: str
    metadata: SeedMetadata = field(default_factory=SeedMetadata)


class CorpusManager:
    def __init__(
        self,
        corpus_dir: str | Path,
        db: FuzzerDatabase,
        target_grammar: str | None = None,
        generator_dir: str | Path | None = None,
        generator_kwargs: dict | None = None,
    ):
        """
        corpus_dir: directory of initial seed files to load at startup (only used on first run).
        db:         database instance used to persist and reload seeds across runs.
        target_grammar: grammar name used for seed generation
        """
        self.corpus_dir = Path(corpus_dir).resolve()
        self.generator_dir = Path(generator_dir).resolve() if generator_dir else None
        self._db = db
        self.target_grammar = target_grammar
        self.generator_kwargs = generator_kwargs or {}
        self._seeds: list[SeedInput] = []

    def load(self) -> None:
        """
        Load seeds from the database if available, otherwise load from corpus_dir files
        and persist them to the database or dynamically generate them if a target_grammar is configured
        1. Load from DB
        2. Load from corpus directory
        3. Generate seeds from grammar if choose grammar in command
        4. Handle empty state (no grammar & no corpus) -> currently : seed = "fuzzer"
        """
        self._seeds = self._db.load_seeds()

        if not self._seeds and self.corpus_dir.exists():
            if self.corpus_dir.exists() and self.corpus_dir.is_dir():
                for path in sorted(self.corpus_dir.iterdir()):
                    if path.is_file():
                        data = path.read_text(encoding="utf-8")
                        seed = SeedInput(data=data)
                        self._db.save_seed(seed)
                        self._seeds.append(seed)

        if not self._seeds and self.target_grammar:
            if not self.generator_dir:
                raise ValueError(
                    f"Generator directory not found or not configured. "
                    f"Expected directory: {self.generator_dir} (required when using {self.target_grammar})"
                )
            generator = GrammarSeedGenerator(
                self.target_grammar, self.generator_dir, **self.generator_kwargs
            )
            generated_strings = generator.generate(count=10)
            for data in generated_strings:
                seed = SeedInput(data=data)
                self._db.save_seed(seed)
                self._seeds.append(seed)

        if not self._seeds:
            data = "fuzzer"
            seed = SeedInput(data=data)
            self._db.save_seed(seed)
            self._seeds.append(seed)

    def seeds(self) -> list[SeedInput]:
        """Return the current list of seeds."""
        return list(self._seeds)

    def add(self, data: str) -> SeedInput:
        """
        Add an interesting input to the in-memory pool and persist it to the database.
        Returns the newly created SeedInput.
        """
        seed = SeedInput(data=data)
        self._db.save_seed(seed)
        self._seeds.append(seed)
        return seed

    def record_picked(self, seed: SeedInput) -> None:
        """Increment the times_picked counter for a seed."""
        seed.metadata.times_picked += 1

    def record_fuzzed(self, seed: SeedInput) -> None:
        """Increment the times_fuzzed counter for a seed."""
        seed.metadata.times_fuzzed += 1
