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

    # Stopping conditions (None = disabled)
    max_iterations: int | None = 1000
    time_limit: int | None = 60  # seconds

    # Scheduler ("random" or "fast")
    scheduler: str = "fast"

    # Mutation strategy
    mutation_strategy: str = "random_single"

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
        self.max_iterations = self._normalise_limit(
            self.max_iterations,
            "max_iterations",
        )
        self.time_limit = self._normalise_limit(self.time_limit, "time_limit")
        self._validate_paths()

    def _validate_paths(self) -> None:
        if not self.project_dir.exists() or not self.project_dir.is_dir():
            raise ValueError(
                f"project_dir does not exist or is not a directory: {self.project_dir}"
            )

        if not self.harness_path.exists() or not self.harness_path.is_file():
            raise ValueError(f"Harness script not found: {self.harness_path}")

        if not self.corpus_dir.exists() or not self.corpus_dir.is_dir():
            raise ValueError(f"Corpus directory not found: {self.corpus_dir}")

    @staticmethod
    def _normalise_limit(value: int | None, name: str) -> int | None:
        """Normalise optional stop limits; accept -1 for backward compatibility."""
        if value is None or value == -1:
            return None
        if value < 0:
            raise ValueError(f"{name} must be >= 0, -1, or None")
        return value
