"""
Corpus manager: loads seed inputs, tracks metadata, and persists via the database.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

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
    def __init__(self, corpus_dir: str | Path, db: FuzzerDatabase):
        """
        corpus_dir: directory of initial seed files to load at startup (only used on first run).
        db:         database instance used to persist and reload seeds across runs.
        """
        self.corpus_dir = Path(corpus_dir).resolve()
        self._db = db
        self._seeds: list[SeedInput] = []

    def load(self) -> None:
        """
        Load seeds from the database if available, otherwise load from corpus_dir files
        and persist them to the database.
        """
        self._seeds = self._db.load_seeds()

        if not self._seeds:
            # First run — load from seed files and persist to DB
            for path in sorted(self.corpus_dir.iterdir()):
                if path.is_file():
                    data = path.read_text(encoding="utf-8")
                    seed = SeedInput(data=data)
                    self._db.save_seed(seed)
                    self._seeds.append(seed)

        if not self._seeds:
            raise ValueError(
                f"No seed files found in corpus directory: {self.corpus_dir}"
            )

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
