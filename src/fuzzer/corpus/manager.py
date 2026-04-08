"""
Corpus manager: loads seed inputs, tracks metadata, and persists via the database.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from fuzzer.grammar.generator import generate_from_grammar

if TYPE_CHECKING:
    from fuzzer.storage.database import FuzzerDatabase

logger = logging.getLogger(__name__)


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
        db: "FuzzerDatabase",
        *,
        grammar_name: str,
    ):
        """
        corpus_dir: directory of initial seed files to load at startup (only used on first run).
        db:         database instance used to persist and reload seeds across runs.
        grammar_name: grammar used for generated first-run seed bootstrap.
        """
        self.corpus_dir = Path(corpus_dir).resolve()
        self.grammar_name = grammar_name
        self._db = db
        self._seeds: list[SeedInput] = []
        self._seed_index: dict[str, SeedInput] = {}

    def load(self) -> None:
        """
        Load seeds from the database if available.
        If empty, generate first-run seeds from grammar and persist them.
        If generation fails or yields no seeds, fall back to corpus_dir files.
        """
        self._seeds = self._db.load_seeds()
        self._rebuild_index()
        self._merge_loaded_duplicates()
        generation_error: Exception | None = None

        if not self._seeds:
            try:
                generated = self._generate_initial_seeds(count=1)
            except Exception as exc:
                generation_error = exc
                generated = []
            for data in generated:
                self._add_seed(data, persist=True)

        if not self._seeds:
            # Fallback — load from seed files and persist to DB
            for path in sorted(self.corpus_dir.iterdir()):
                if path.is_file():
                    for data in self._load_seed_file(path):
                        self._add_seed(data, persist=True)
            if self._seeds and generation_error is not None:
                logger.warning(
                    "Initial seed generation failed for grammar %r; using corpus files "
                    "fallback from %s. Error: %r",
                    self.grammar_name,
                    self.corpus_dir,
                    generation_error,
                )

        if not self._seeds:
            error = ValueError(
                "No initial seeds available. "
                f"Grammar generation failed for {self.grammar_name!r}, "
                f"and no seed files were found in corpus directory: {self.corpus_dir}"
            )
            if generation_error is not None:
                raise error from generation_error
            raise error

    def _generate_initial_seeds(self, count: int) -> list[str]:
        generated: list[str] = []
        for _ in range(count):
            generated.append(generate_from_grammar(self.grammar_name, max_depth=8))
        return generated

    def _add_seed(self, data: str, *, persist: bool) -> SeedInput:
        existing = self._seed_index.get(data)
        if existing is not None:
            return existing

        seed = SeedInput(data=data)
        if persist:
            self._db.save_seed(seed)
        self._seeds.append(seed)
        self._seed_index[data] = seed
        return seed

    def _rebuild_index(self) -> None:
        self._seed_index = {seed.data: seed for seed in self._seeds}

    def _merge_loaded_duplicates(self) -> None:
        if not self._seeds:
            return

        merged: dict[str, SeedInput] = {}
        ordered_data: list[str] = []

        for seed in self._seeds:
            existing = merged.get(seed.data)
            if existing is None:
                merged[seed.data] = SeedInput(
                    data=seed.data,
                    metadata=SeedMetadata(
                        times_picked=seed.metadata.times_picked,
                        times_fuzzed=seed.metadata.times_fuzzed,
                    ),
                )
                ordered_data.append(seed.data)
            else:
                existing.metadata.times_picked += seed.metadata.times_picked
                existing.metadata.times_fuzzed += seed.metadata.times_fuzzed

        self._seeds = [merged[data] for data in ordered_data]
        self._seed_index = merged

    def _load_seed_file(self, path: Path) -> list[str]:
        if path.suffix.lower() != ".json":
            return [path.read_text(encoding="utf-8")]

        text = path.read_text(encoding="utf-8")
        payload = json.loads(text)

        if isinstance(payload, list):
            seeds: list[str] = []
            for item in payload:
                if isinstance(item, str):
                    seeds.append(item)
                else:
                    seeds.append(
                        json.dumps(item, ensure_ascii=False, separators=(",", ":"))
                    )
            return seeds

        if isinstance(payload, str):
            return [payload]

        return [json.dumps(payload, ensure_ascii=False, separators=(",", ":"))]

    def seeds(self) -> list[SeedInput]:
        """Return the current list of seeds."""
        return list(self._seeds)

    def size(self) -> int:
        """Return the number of seeds currently in the in-memory corpus."""
        return len(self._seeds)

    def get(self, index: int) -> SeedInput:
        """Return a seed by index from the live in-memory corpus."""
        return self._seeds[index]

    def add(self, data: str) -> SeedInput:
        """
        Add an interesting input to the in-memory pool and persist it to the database.
        Returns the newly created SeedInput.
        """
        return self._add_seed(data, persist=True)

    def record_picked(self, seed: SeedInput) -> None:
        """Increment the times_picked counter for a seed."""
        seed.metadata.times_picked += 1

    def record_fuzzed(self, seed: SeedInput) -> None:
        """Increment the times_fuzzed counter for a seed."""
        seed.metadata.times_fuzzed += 1
