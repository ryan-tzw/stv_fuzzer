"""
Configuration for the fuzzing engine.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Standard base directories relative to this package
_PACKAGE_DIR = Path(__file__).parent
HARNESSES_DIR = _PACKAGE_DIR / "harnesses"
CORPUS_DIR = _PACKAGE_DIR / "corpus"


PROFILE_CONFIGS: dict[str, dict[str, Any]] = {
    "json_decoder": {
        "project_dir": Path("targets/json-decoder"),
        "harness": "json-decoder",
        "corpus": "json",
        "mode": "coverage",
    },
    "ipv4_parser": {
        "project_dir": Path("targets/_reference/ipyparse"),
        "harness": "ipyparse",
        "corpus": "ipv4",
        "mode": "differential",
        "harness_args": ("--family", "ipv4"),
        "blackbox_binary": Path("targets/IPv4-IPv6-parser/bin/linux-ipv4-parser"),
        "blackbox_input_flag": "--ipstr",
    },
    "ipv6_parser": {
        "project_dir": Path("targets/_reference/ipyparse"),
        "harness": "ipyparse",
        "corpus": "ipv6",
        "mode": "differential",
        "harness_args": ("--family", "ipv6"),
        "blackbox_binary": Path("targets/IPv4-IPv6-parser/bin/linux-ipv6-parser"),
        "blackbox_input_flag": "--ipstr",
    },
    "cidrize_ipv4": {
        "project_dir": Path("targets/_reference/cidrize"),
        "harness": "cidrize",
        "corpus": "ipv4",
        "mode": "differential",
        "blackbox_binary": Path("targets/cidrize-runner/bin/linux-cidrize-runner"),
        "blackbox_input_flag": "--ipstr",
        "blackbox_args": ("--func", "cidrize", "--raise-errors"),
    },
    "cidrize_ipv6": {
        "project_dir": Path("targets/_reference/cidrize"),
        "harness": "cidrize",
        "corpus": "ipv6",
        "mode": "differential",
        "blackbox_binary": Path("targets/cidrize-runner/bin/linux-cidrize-runner"),
        "blackbox_input_flag": "--ipstr",
        "blackbox_args": ("--func", "cidrize", "--raise-errors"),
    },
}


def available_profiles() -> tuple[str, ...]:
    """Return the sorted list of built-in profile names."""
    return tuple(sorted(PROFILE_CONFIGS))


def profile_overrides(name: str) -> dict[str, Any]:
    """Return profile key/value overrides for *name*."""
    try:
        return dict(PROFILE_CONFIGS[name])
    except KeyError as exc:
        raise ValueError(f"Unknown profile: {name!r}") from exc


@dataclass
class FuzzerConfig:
    # Target
    project_dir: Path
    harness: str  # name of the harness script (without .py)
    corpus: str  # name of the corpus type directory

    # Execution mode
    mode: str = "coverage"  # "coverage" or "differential"

    # Harness arguments (passed to whitebox harness)
    harness_args: tuple[str, ...] = ()

    # Differential blackbox target options
    blackbox_binary: Path | None = None
    blackbox_input_flag: str = "--ipstr"
    blackbox_args: tuple[str, ...] = ()
    diff_use_whitebox_coverage: bool = True
    diff_use_blackbox_nonzero_exit: bool = False
    diff_use_blackbox_traceback: bool = False
    diff_use_exit_code_mismatch: bool = False
    diff_use_blackbox_stderr: bool = False
    diff_use_whitebox_nonzero_exit: bool = False

    # Output
    runs_dir: Path = Path("runs")

    # Stopping conditions (None = disabled)
    max_cycles: int | None = None
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
        if self.blackbox_binary is not None:
            self.blackbox_binary = Path(self.blackbox_binary).resolve()
        self.harness_args = tuple(self.harness_args)
        self.blackbox_args = tuple(self.blackbox_args)
        self.max_cycles = self._normalise_limit(self.max_cycles, "max_cycles")
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

        if self.mode not in {"coverage", "differential"}:
            raise ValueError(f"Unknown execution mode: {self.mode!r}")

        if self.mode == "differential":
            if self.blackbox_binary is None:
                raise ValueError("blackbox_binary is required in differential mode")
            if not self.blackbox_binary.exists() or not self.blackbox_binary.is_file():
                raise ValueError(
                    "blackbox_binary does not exist or is not a file: "
                    f"{self.blackbox_binary}"
                )

    @staticmethod
    def _normalise_limit(value: int | None, name: str) -> int | None:
        """Normalise optional stop limits; accept -1 for backward compatibility."""
        if value is None or value == -1:
            return None
        if value < 0:
            raise ValueError(f"{name} must be >= 0, -1, or None")
        return value
