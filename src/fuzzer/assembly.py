"""Default assembly of engine components.

This module provides a small seam for constructing runtime components so the
engine can accept injected dependencies in tests or alternate pipelines.
"""

from dataclasses import dataclass

from fuzzer.config import FuzzerConfig
from fuzzer.core import Mutator
from fuzzer.core.mutator import build_strategy
from fuzzer.core.scheduler import FastScheduler, RandomScheduler, Scheduler
from fuzzer.executors import Executor, PersistentCoverageExecutor
from fuzzer.feedback import CoverageFeedback, CrashDetector, ExitCodeCrashDetector
from fuzzer.observers.python_coverage import InProcessCoverageObserver


@dataclass
class EngineComponents:
    mutator: Mutator
    scheduler: Scheduler
    executor: Executor
    observer: InProcessCoverageObserver
    feedback: CoverageFeedback
    crash_detector: CrashDetector


def build_engine_components(config: FuzzerConfig) -> EngineComponents:
    return EngineComponents(
        mutator=_build_mutator(config),
        scheduler=_build_scheduler(config),
        executor=PersistentCoverageExecutor(config.project_dir, config.harness_path),
        observer=InProcessCoverageObserver(config.project_dir),
        feedback=CoverageFeedback(),
        crash_detector=ExitCodeCrashDetector(),
    )


def _build_scheduler(config: FuzzerConfig) -> Scheduler:
    if config.scheduler == "fast":
        return FastScheduler(c=config.energy_c, max_energy=config.max_energy)
    if config.scheduler == "random":
        return RandomScheduler()
    raise ValueError(f"Unknown scheduler: {config.scheduler!r}")


def _build_mutator(config: FuzzerConfig) -> Mutator:
    return Mutator(strategy=build_strategy(config.mutation_strategy))
