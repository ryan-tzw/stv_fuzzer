"""
Fuzzing engine: orchestrates the main fuzzing loop.
"""

import time
from datetime import datetime

from fuzzer.config import FuzzerConfig
from fuzzer.core import CorpusManager, Mutator
from fuzzer.core.scheduler import FastScheduler, RandomScheduler, Scheduler
from fuzzer.executors.python_coverage import PythonCoverageExecutor
from fuzzer.feedback import CoverageFeedback
from fuzzer.observers.python_coverage import PythonCoverageObserver
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
        self.executor = PythonCoverageExecutor(config.project_dir, config.harness_path)
        self.observer = PythonCoverageObserver(config.project_dir)
        self.feedback = CoverageFeedback()

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
        print(
            f"Loaded {len(self.corpus.seeds())} seed(s) from {self.config.corpus_dir}"
        )
        print(f"Run output: {self.run_dir}")

        iteration = 0
        unique_crashes = 0
        start_time = time.monotonic()

        try:
            while True:
                # Check stopping conditions
                if (
                    self.config.max_iterations != -1
                    and iteration >= self.config.max_iterations
                ):
                    print(f"Reached max iterations ({self.config.max_iterations}).")
                    break
                if self.config.time_limit != -1:
                    elapsed = time.monotonic() - start_time
                    if elapsed >= self.config.time_limit:
                        print(f"Reached time limit ({self.config.time_limit}s).")
                        break

                # Pick seed and compute energy
                seed = self.scheduler.next(self.corpus.seeds())
                self.corpus.record_picked(seed)
                energy = self.scheduler.energy(seed)

                for _ in range(energy):
                    mutated = self.mutator.mutate(seed.data)

                    stdout, stderr, coverage_file = self.executor.run(mutated)
                    self.corpus.record_fuzzed(seed)

                    signal = self.observer.observe(coverage_file)
                    result = self.feedback.evaluate(signal, stderr)

                    if result.is_crash:
                        is_new = self.db.record_crash(mutated, stderr)
                        if is_new:
                            unique_crashes += 1
                            print(
                                f"[iter {iteration}] New unique crash! Total unique: {unique_crashes}"
                            )
                        else:
                            print(
                                f"[iter {iteration}] Duplicate crash (not recorded again)."
                            )

                    if result.add_to_corpus:
                        self.corpus.add(mutated)
                        print(
                            f"[iter {iteration}] New coverage found — corpus size: {len(self.corpus.seeds())}"
                        )

                    iteration += 1

        except KeyboardInterrupt:
            print("\nFuzzing interrupted.")

        finally:
            self.db.flush_corpus(self.corpus.seeds())
            self.db.close()

        elapsed = time.monotonic() - start_time
        print(f"\nDone. {iteration} iterations in {elapsed:.1f}s.")
        print(
            f"Corpus size: {len(self.corpus.seeds())} | Unique crashes: {unique_crashes}"
        )
        print(f"Results: {self.run_dir / 'results.db'}")
