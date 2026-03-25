"""
Schedulers: determine which seed to pick next from the corpus,
and how much energy (number of mutations) to apply to it.
"""

import random
from abc import ABC, abstractmethod

from .corpus import SeedInput

DEFAULT_ENERGY = 10


class Scheduler(ABC):
    @abstractmethod
    def next(self, seeds: list[SeedInput]) -> SeedInput:
        """Select the next seed to fuzz from the given list."""
        ...

    @abstractmethod
    def energy(self, seed: SeedInput) -> int:
        """Return the number of mutations to apply to the selected seed."""
        ...


class RandomScheduler(Scheduler):
    """Pick a seed uniformly at random with fixed energy."""

    def __init__(self, energy: int = DEFAULT_ENERGY):
        self._energy = energy

    def next(self, seeds: list[SeedInput]) -> SeedInput:
        if not seeds:
            raise ValueError("Cannot schedule from an empty seed pool.")
        return random.choice(seeds)

    def energy(self, seed: SeedInput) -> int:
        return self._energy


class FastScheduler(Scheduler):
    """
    AFL-Fast exponential power schedule.

    Energy formula:
        p(i) = min(c * 2^s(i) / f(i), M)

    Where:
        c   = normalised base energy constant (alpha / beta)
        s(i) = times seed i was picked from the queue
        f(i) = times seed i was fuzzed + 1 (to avoid division by zero)
        M   = hard cap on energy
    """

    def __init__(self, c: float = 1.0, max_energy: int = 10_000):
        self.c = c
        self.max_energy = max_energy

    def next(self, seeds: list[SeedInput]) -> SeedInput:
        if not seeds:
            raise ValueError("Cannot schedule from an empty seed pool.")
        return random.choice(seeds)

    def energy(self, seed: SeedInput) -> int:
        s = seed.metadata.times_picked
        f = seed.metadata.times_fuzzed + 1
        raw = self.c * (2**s) / f
        return max(1, min(int(raw), self.max_energy))
