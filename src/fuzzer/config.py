"""
Configuration for the fuzzing engine.
"""

from dataclasses import dataclass
from pathlib import Path

# Standard base directories relative to this package
_PACKAGE_DIR = Path(__file__).parent
HARNESSES_DIR = _PACKAGE_DIR / "harnesses"
CORPUS_DIR = _PACKAGE_DIR / "core" / "corpus"


@dataclass
class FuzzerConfig:
    # Target
    project_dir: Path
    harness: str  # name of the harness script (without .py)
    corpus: str  # name of the corpus type directory

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

    @property
    def harness_path(self) -> Path:
        return HARNESSES_DIR / f"{self.harness}.py"

    @property
    def corpus_dir(self) -> Path:
        return CORPUS_DIR / self.corpus

    def __post_init__(self) -> None:
        self.project_dir = Path(self.project_dir).resolve()
        self.runs_dir = Path(self.runs_dir).resolve()
