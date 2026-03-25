"""Default assembly of engine components.

This module provides a small seam for constructing runtime components so the
engine can accept injected dependencies in tests or alternate pipelines.
"""

from dataclasses import dataclass
from typing import Any

from fuzzer.config import FuzzerConfig
from fuzzer.mutator import Mutator, build_strategy
from fuzzer.schedulers import FastScheduler, RandomScheduler, Scheduler
from fuzzer.executors import (
    BinaryExecutor,
    DifferentialExecutor,
    Executor,
    PersistentCoverageExecutor,
)
from fuzzer.feedback import (
    CoverageFeedback,
    CrashDetector,
    DifferentialFeedback,
    ExitCodeCrashDetector,
    ExitCodeOrOutputCrashDetector,
)
from fuzzer.observers import DifferentialObserver, InProcessCoverageObserver


@dataclass
class EngineComponents:
    mutator: Mutator
    scheduler: Scheduler
    executor: Executor
    observer: Any
    feedback: Any
    crash_detector: CrashDetector


def build_engine_components(config: FuzzerConfig) -> EngineComponents:
    if config.mode == "differential":
        if config.blackbox_binary is None:
            raise ValueError("blackbox_binary is required in differential mode")

        return EngineComponents(
            mutator=_build_mutator(config),
            scheduler=_build_scheduler(config),
            executor=DifferentialExecutor(
                blackbox=BinaryExecutor(
                    binary_path=config.blackbox_binary,
                    input_flag=config.blackbox_input_flag,
                    static_args=list(config.blackbox_args),
                ),
                whitebox=PersistentCoverageExecutor(
                    config.project_dir,
                    config.harness_path,
                    script_args=list(config.harness_args),
                ),
            ),
            observer=DifferentialObserver(config.project_dir),
            feedback=DifferentialFeedback(),
            crash_detector=ExitCodeOrOutputCrashDetector(),
        )

    return EngineComponents(
        mutator=_build_mutator(config),
        scheduler=_build_scheduler(config),
        executor=PersistentCoverageExecutor(
            config.project_dir,
            config.harness_path,
            script_args=list(config.harness_args),
        ),
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
