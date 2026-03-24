from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fuzzer.executors import PersistentCoverageExecutor
from fuzzer.executors.command import CommandExecutor
from fuzzer.feedback import BlackboxFeedback, CoverageFeedback
from fuzzer.observers.blackbox import BlackboxObserver
from fuzzer.observers.python_coverage import InProcessCoverageObserver


@dataclass(frozen=True)
class TargetProfile:
    name: str
    grammar_name: str
    execution_mode: str
    binary_relpath: str | None = None
    base_args: tuple[str, ...] = ()
    input_arg: str | None = None
    timeout_seconds: float = 5.0

    def build_executor(self, project_dir: Path, harness_path: Path):
        if self.execution_mode == "coverage_python":
            return PersistentCoverageExecutor(project_dir, harness_path)
        if self.execution_mode == "command":
            binary_path = project_dir / (self.binary_relpath or "")
            return CommandExecutor(
                command=[str(binary_path), *self.base_args],
                cwd=project_dir,
                timeout_seconds=self.timeout_seconds,
                input_mode="arg",
                input_arg=self.input_arg,
            )
        raise ValueError(f"Unknown execution mode: {self.execution_mode}")

    def build_observer(self, project_dir: Path):
        if self.execution_mode == "coverage_python":
            return InProcessCoverageObserver(project_dir)
        if self.execution_mode == "command":
            return BlackboxObserver()
        raise ValueError(f"Unknown execution mode: {self.execution_mode}")

    def build_feedback(self):
        if self.execution_mode == "coverage_python":
            return CoverageFeedback()
        if self.execution_mode == "command":
            return BlackboxFeedback()
        raise ValueError(f"Unknown execution mode: {self.execution_mode}")


_TARGETS: dict[str, TargetProfile] = {
    "json-decoder": TargetProfile(
        name="json-decoder",
        grammar_name="json",
        execution_mode="coverage_python",
    ),
    "ipv4-parser": TargetProfile(
        name="ipv4-parser",
        grammar_name="ipv4",
        execution_mode="command",
        binary_relpath="bin/mac-ipv4-parser",
        input_arg="--ipstr",
        timeout_seconds=180.0,
    ),
    "ipv6-parser": TargetProfile(
        name="ipv6-parser",
        grammar_name="ipv6",
        execution_mode="command",
        binary_relpath="bin/mac-ipv6-parser",
        input_arg="--ipstr",
        timeout_seconds=180.0,
    ),
    "cidrize-runner": TargetProfile(
        name="cidrize-runner",
        grammar_name="cidrize",
        execution_mode="command",
        binary_relpath="bin/mac-cidrize-runner",
        base_args=("--func", "cidrize", "--raise-errors"),
        input_arg="--ipstr",
        timeout_seconds=180.0,
    ),
}


def get_target_profile(name: str) -> TargetProfile:
    normalised = name.strip().lower()
    try:
        return _TARGETS[normalised]
    except KeyError as exc:
        available = ", ".join(sorted(_TARGETS))
        raise ValueError(
            f"Unknown target profile {name!r}. Available: {available}"
        ) from exc
