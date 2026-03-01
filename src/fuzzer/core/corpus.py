"""
Corpus manager: loads seed inputs, tracks metadata, and saves interesting inputs to disk.
"""

import uuid
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SeedMetadata:
    times_picked: int = 0
    times_fuzzed: int = 0


@dataclass
class SeedInput:
    data: str
    metadata: SeedMetadata = field(default_factory=SeedMetadata)


class CorpusManager:
    def __init__(self, corpus_dir: str | Path, save_dir: str | Path):
        """
        corpus_dir: directory of initial seed files to load at startup.
        save_dir:   directory where interesting inputs discovered during fuzzing are saved.
        """
        self.corpus_dir = Path(corpus_dir).resolve()
        self.save_dir = Path(save_dir).resolve()
        self._seeds: list[SeedInput] = []

    def load(self) -> None:
        """Load all files from corpus_dir into memory as SeedInputs."""
        self._seeds.clear()
        for path in sorted(self.corpus_dir.iterdir()):
            if path.is_file():
                data = path.read_text(encoding="utf-8")
                self._seeds.append(SeedInput(data=data))

        if not self._seeds:
            raise ValueError(
                f"No seed files found in corpus directory: {self.corpus_dir}"
            )

    def seeds(self) -> list[SeedInput]:
        """Return the current list of seeds."""
        return list(self._seeds)

    def add(self, data: str) -> SeedInput:
        """
        Save an interesting input to disk and add it to the in-memory pool.
        Returns the newly created SeedInput.
        """
        self.save_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid.uuid4().hex}.json"
        (self.save_dir / filename).write_text(data, encoding="utf-8")

        seed = SeedInput(data=data)
        self._seeds.append(seed)
        return seed

    def record_picked(self, seed: SeedInput) -> None:
        """Increment the times_picked counter for a seed."""
        seed.metadata.times_picked += 1

    def record_fuzzed(self, seed: SeedInput) -> None:
        """Increment the times_fuzzed counter for a seed."""
        seed.metadata.times_fuzzed += 1
