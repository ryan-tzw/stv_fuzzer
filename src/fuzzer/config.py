"""
Configuration for the fuzzing engine.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class FuzzerConfig:
    # Target
    project_dir: Path
    harness_path: Path
    corpus_dir: Path

    # Output
    runs_dir: Path = Path("runs")

    # Stopping conditions (-1 = disabled)
    max_iterations: int = 1000
    time_limit: int = 60  # seconds

    # Scheduler ("random" or "fast")
    scheduler: str = "fast"

    # FastScheduler parameters
    energy_c: float = 1.0
    max_energy: int = 100

    def __post_init__(self) -> None:
        self.project_dir = Path(self.project_dir).resolve()
        self.harness_path = Path(self.harness_path).resolve()
        self.corpus_dir = Path(self.corpus_dir).resolve()
        self.runs_dir = Path(self.runs_dir).resolve()
