"""
Fuzzing engine: orchestrates the main fuzzing loop.
"""

import time
from datetime import datetime

from fuzzer.config import FuzzerConfig
from fuzzer.core import CorpusManager, Mutator
from fuzzer.core.scheduler import FastScheduler, RandomScheduler, Scheduler
from fuzzer.executors import PersistentCoverageExecutor
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
        self.executor = PersistentCoverageExecutor(
            config.project_dir, config.harness_path
        )
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

    def run(self) -> None:
        self.corpus.load()

        iteration = 0
        unique_crashes = 0
        start_time = time.monotonic()
        label_count = {}

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

                        start = time.perf_counter()
                        duration_ms = (time.perf_counter() - start) * 1000

                        stdout, stderr, exit_code, coverage_file = self.executor.run(
                            mutated
                        )
                        self.corpus.record_fuzzed(seed)

                        signal = self.observer.observe(coverage_file)
                        result = self.feedback.evaluate(
                            mutated, exit_code, duration_ms, signal, stderr
                        )

                        for label in result.labels:
                            if label not in label_count:
                                label_count[label] = 0
                            label_count[label] += 1

                        if result.labels:
                            self.logger.log_debug(
                                f"[{iteration}] labels={result.labels} len={len(mutated)} input={repr(mutated)} exit={exit_code} time={duration_ms:.2f} ms"
                                # self.logger.log_debug(f"[{iteration}] stderr_tail={stderr[-1000:]} input={mutated}")
                            )

                        if result.is_crash:
                            is_new = self.db.record_crash(mutated, stderr)
                            if is_new:
                                unique_crashes += 1
                                self.logger.log_crash(
                                    iteration,
                                    unique_crashes,
                                    mutated,
                                    result.labels,
                                    exit_code,
                                )
                            else:
                                self.logger.log_duplicate_crash(iteration)

                        if result.add_to_corpus:
                            self.corpus.add(mutated)
                            self.logger.log_corpus_add(
                                iteration, mutated, result.labels
                            )

                        iteration += 1
                        self.logger.tick(iteration)

            except KeyboardInterrupt:
                self.logger.log_stop_reason("interrupted by user")

            finally:
                self.db.flush_corpus(self.corpus.seeds())
                self.db.close()

        elapsed = time.monotonic() - start_time
        self.logger.print_summary(iteration, elapsed)

        self.logger.print_categories_crashes(label_count)
