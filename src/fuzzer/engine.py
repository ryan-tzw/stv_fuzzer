"""
Fuzzing engine: orchestrates the main fuzzing loop.
"""

import time
from datetime import datetime

from fuzzer.assembly import EngineComponents, build_engine_components
from fuzzer.config import FuzzerConfig
from fuzzer.core import CorpusManager
from fuzzer.logger import FuzzerLogger
from fuzzer.storage.database import FuzzerDatabase


class FuzzingEngine:
    def __init__(
        self, config: FuzzerConfig, components: EngineComponents | None = None
    ):
        self.config = config

        # Set up run output directory and database
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = config.runs_dir / run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)

        self.db = FuzzerDatabase(self.run_dir / "results.db")
        self.corpus = CorpusManager(config.corpus_dir, self.db)
        runtime_components = components or build_engine_components(config)
        self.mutator = runtime_components.mutator
        self.scheduler = runtime_components.scheduler
        self.executor = runtime_components.executor
        self.observer = runtime_components.observer
        self.feedback = runtime_components.feedback
        self.crash_detector = runtime_components.crash_detector
        self.logger = FuzzerLogger(self.run_dir, config)

    def _stop_reason(self, iteration: int, start_time: float) -> str | None:
        max_iterations = self.config.max_iterations
        if max_iterations is not None and iteration >= max_iterations:
            return f"reached max iterations ({max_iterations})"

        time_limit = self.config.time_limit
        if time_limit is not None:
            elapsed = time.monotonic() - start_time
            if elapsed >= time_limit:
                return f"reached time limit ({time_limit}s)"

        return None

    def _process_seed(
        self, seed, iteration: int, unique_crashes: int
    ) -> tuple[int, int]:
        """Run fuzz iterations for one selected seed and update counters."""
        self.corpus.record_picked(seed)
        energy = self.scheduler.energy(seed)

        for _ in range(energy):
            mutated = self.mutator.mutate(seed.data)

            run_result = self.executor.run(mutated)
            self.corpus.record_fuzzed(seed)

            signal = self.observer.observe(run_result.result)
            add_to_corpus = self.feedback.evaluate(signal)
            is_crash = self.crash_detector.is_crash(
                exit_code=run_result.exit_code,
                stderr=run_result.stderr,
            )

            if is_crash:
                is_new = self.db.record_crash(mutated, run_result.stderr)
                if is_new:
                    unique_crashes += 1
                    self.logger.log_crash(iteration, unique_crashes)
                else:
                    self.logger.log_duplicate_crash(iteration)

            if add_to_corpus:
                self.corpus.add(mutated)
                self.logger.log_corpus_add(iteration)

            iteration += 1
            self.logger.tick(iteration)

        return iteration, unique_crashes

    def run(self) -> None:
        self.corpus.load()

        iteration = 0
        unique_crashes = 0
        start_time = time.monotonic()

        with self.logger:
            self.logger.start(corpus_size=len(self.corpus.seeds()))

            try:
                while True:
                    stop_reason = self._stop_reason(iteration, start_time)
                    if stop_reason is not None:
                        self.logger.log_stop_reason(stop_reason)
                        break

                    seed = self.scheduler.next(self.corpus.seeds())
                    iteration, unique_crashes = self._process_seed(
                        seed, iteration, unique_crashes
                    )

            except KeyboardInterrupt:
                self.logger.log_stop_reason("interrupted by user")

            finally:
                self.db.flush_corpus(self.corpus.seeds())
                self.db.close()

        elapsed = time.monotonic() - start_time
        self.logger.print_summary(iteration, elapsed)
