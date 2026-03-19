"""
Fuzzing engine: orchestrates the main fuzzing loop.
"""

import time
from datetime import datetime

from fuzzer.config import FuzzerConfig
from fuzzer.core import CorpusManager, Mutator
from fuzzer.core.scheduler import FastScheduler, RandomScheduler, Scheduler
from fuzzer.executors import (
    DifferentialExecutor,
    InProcessCoverageExecutor,
    PersistentCoverageExecutor,
)
from fuzzer.feedback import CoverageFeedback
from fuzzer.logger import FuzzerLogger
from fuzzer.observers.python_coverage import (
    InProcessCoverageObserver,
)
from fuzzer.storage.database import FuzzerDatabase


class FuzzingEngine:
    def __init__(self, config: FuzzerConfig):
        self.config = config

        # Set up run output directory and database
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = config.runs_dir / run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)

        self.db = FuzzerDatabase(self.run_dir / "results.db")
        self.corpus = CorpusManager(config.corpus_dir, self.db)
        self.mutator = Mutator()
        self.scheduler = self._build_scheduler()
        self.executor = self._build_executor(config)
        self.observer = InProcessCoverageObserver(config.project_dir)
        self.feedback = CoverageFeedback()
        self.logger = FuzzerLogger(self.run_dir, config)

    def _build_scheduler(self) -> Scheduler:
        if self.config.scheduler == "fast":
            return FastScheduler(
                c=self.config.energy_c, max_energy=self.config.max_energy
            )
        elif self.config.scheduler == "random":
            return RandomScheduler()
        else:
            raise ValueError(f"Unknown scheduler: {self.config.scheduler!r}")

    def _build_executor(self, config: FuzzerConfig):
        """Construct the chosen executor implementation."""
        if config.executor == "persistent":
            return PersistentCoverageExecutor(config.project_dir, config.harness_path)
        if config.executor == "inprocess":
            return InProcessCoverageExecutor(config.project_dir, config.harness_path)
        if config.executor == "differential":
            if not config.blackbox_cmd:
                raise ValueError(
                    "--blackbox-cmd is required when --executor=differential"
                )
            import shlex

            black_cmd = shlex.split(config.blackbox_cmd)
            return DifferentialExecutor(
                black_cmd,
                PersistentCoverageExecutor(config.project_dir, config.harness_path),
            )
        raise ValueError(f"Unknown executor: {config.executor!r}")

    def run(self) -> None:
        self.corpus.load()
        self.executor.start()

        iteration = 0
        unique_crashes = 0
        start_time = time.monotonic()

        with self.logger:
            self.logger.start(corpus_size=len(self.corpus.seeds()))

            try:
                while True:
                    # Check stopping conditions
                    if (
                        self.config.max_iterations != -1
                        and iteration >= self.config.max_iterations
                    ):
                        self.logger.log_stop_reason(
                            f"reached max iterations ({self.config.max_iterations})"
                        )
                        break
                    if self.config.time_limit != -1:
                        elapsed = time.monotonic() - start_time
                        if elapsed >= self.config.time_limit:
                            self.logger.log_stop_reason(
                                f"reached time limit ({self.config.time_limit}s)"
                            )
                            break

                    # Pick seed and compute energy
                    seed = self.scheduler.next(self.corpus.seeds())
                    self.corpus.record_picked(seed)
                    energy = self.scheduler.energy(seed)

                    for _ in range(energy):
                        mutated = self.mutator.mutate(seed.data)

                        exec_result = self.executor.run(mutated)
                        self.corpus.record_fuzzed(seed)

                        signal = self.observer.observe(exec_result.raw_coverage)
                        result = self.feedback.evaluate(signal, exec_result.stderr)

                        if result.is_crash:
                            is_new = self.db.record_crash(mutated, exec_result.stderr)
                            if is_new:
                                unique_crashes += 1
                                self.logger.log_crash(iteration, unique_crashes)
                            else:
                                self.logger.log_duplicate_crash(iteration)

                        if result.add_to_corpus:
                            self.corpus.add(mutated)
                            self.logger.log_corpus_add(iteration)

                        iteration += 1
                        self.logger.tick(iteration)

            except KeyboardInterrupt:
                self.logger.log_stop_reason("interrupted by user")

            finally:
                self.executor.stop()
                self.db.flush_corpus(self.corpus.seeds())
                self.db.close()

        elapsed = time.monotonic() - start_time
        self.logger.print_summary(iteration, elapsed)
