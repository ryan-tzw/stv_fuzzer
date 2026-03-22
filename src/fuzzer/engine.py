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
        self.corpus = CorpusManager(
            config.corpus_dir,
            self.db,
            self.config.grammar,
            self.config.generator_dir,
            self.config.generator_kwargs,
        )
        self.mutator = self._build_mutator()
        self.scheduler = self._build_scheduler()
        self.executor = PersistentCoverageExecutor(
            config.project_dir, config.harness_path
        )
        self.observer = InProcessCoverageObserver(config.project_dir)
        self.feedback = CoverageFeedback()
        self.logger = FuzzerLogger(self.run_dir, config)

    def _build_mutator(self) -> Mutator:
        if not self.config.grammar:
            from .core.mutator.strategies import BlindRandomStrategy

            return Mutator(strategy=BlindRandomStrategy())

        if self.config.grammar == "json":
            from .grammars.parser.parser import jsonParser
            from .grammars.operations.jsonOperations import JsonGrammarOperations
            from .core.mutator.strategies import GrammarStrategy

            strategy = GrammarStrategy(
                jsonParser(self.config.antlr_dir), JsonGrammarOperations()
            )
            return Mutator(strategy=strategy)
        elif self.config.grammar == "ip":
            from .grammars.parser.parser import ipParser
            from .grammars.operations.ipOperations import IpGrammarOperations
            from .core.mutator.strategies import GrammarStrategy

            strategy = GrammarStrategy(
                ipParser(self.config.antlr_dir), IpGrammarOperations()
            )
            return Mutator(strategy=strategy)
        raise ValueError(f"Unknown grammar configuration: {self.config.grammar}")

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
                        mutated = self.mutator.mutate(
                            seed.data, depth=self.config.mutate_depth
                        )

                        stdout, stderr, coverage_file = self.executor.run(mutated)
                        self.corpus.record_fuzzed(seed)

                        signal = self.observer.observe(coverage_file)
                        result = self.feedback.evaluate(signal, stderr)

                        if result.is_crash:
                            is_new = self.db.record_crash(mutated, stderr)
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
                self.db.flush_corpus(self.corpus.seeds())
                self.db.close()

        elapsed = time.monotonic() - start_time
        self.logger.print_summary(iteration, elapsed)
