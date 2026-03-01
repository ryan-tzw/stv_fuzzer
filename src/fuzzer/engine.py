"""
Fuzzing engine: orchestrates the main fuzzing loop.
"""

import time
from datetime import datetime

from fuzzer.config import FuzzerConfig
from fuzzer.core import CorpusManager, Mutator
from fuzzer.core.scheduler import FastScheduler, RandomScheduler, Scheduler
from fuzzer.executors.python_coverage import PythonCoverageExecutor
from fuzzer.observers.python_coverage import CoverageData, PythonCoverageObserver


class FuzzingEngine:
    def __init__(self, config: FuzzerConfig):
        self.config = config

        # Set up run output directories
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = config.runs_dir / run_id
        self.crashes_dir = self.run_dir / "crashes"
        self.interesting_dir = self.run_dir / "corpus"

        self.corpus = CorpusManager(config.corpus_dir, self.interesting_dir)
        self.mutator = Mutator()
        self.scheduler = self._build_scheduler()
        self.executor = PythonCoverageExecutor(config.project_dir, config.harness_path)
        self.observer = PythonCoverageObserver(config.project_dir)

        # Global coverage seen across all runs
        self._seen_lines: set[tuple[str, int]] = set()
        self._seen_branches: set[tuple[str, tuple[int, int]]] = set()

    def _build_scheduler(self) -> Scheduler:
        if self.config.scheduler == "fast":
            return FastScheduler(
                c=self.config.energy_c, max_energy=self.config.max_energy
            )
        elif self.config.scheduler == "random":
            return RandomScheduler()
        else:
            raise ValueError(f"Unknown scheduler: {self.config.scheduler!r}")

    def _is_interesting(self, coverage: CoverageData) -> bool:
        """Return True if coverage contains any lines or branches not seen before."""
        for file, lines in coverage.lines.items():
            for line in lines:
                if (file, line) not in self._seen_lines:
                    return True
        for file, branches in coverage.branches.items():
            for branch in branches:
                if (file, branch) not in self._seen_branches:
                    return True
        return False

    def _update_seen_coverage(self, coverage: CoverageData) -> None:
        for file, lines in coverage.lines.items():
            for line in lines:
                self._seen_lines.add((file, line))
        for file, branches in coverage.branches.items():
            for branch in branches:
                self._seen_branches.add((file, branch))

    def _save_crash(self, data: str) -> None:
        self.crashes_dir.mkdir(parents=True, exist_ok=True)
        from uuid import uuid4

        path = self.crashes_dir / f"{uuid4().hex}.txt"
        path.write_text(data, encoding="utf-8")

    def run(self) -> None:
        self.corpus.load()
        print(
            f"Loaded {len(self.corpus.seeds())} seed(s) from {self.config.corpus_dir}"
        )
        print(f"Run output: {self.run_dir}")

        iteration = 0
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

                    # Detect crash (harness exits non-zero on exception)
                    crashed = "ERR:" in stderr
                    if crashed:
                        print(f"[iter {iteration}] Crash found!")
                        self._save_crash(mutated)

                    coverage = self.observer.observe(coverage_file)

                    if self._is_interesting(coverage):
                        self._update_seen_coverage(coverage)
                        self.corpus.add(mutated)
                        print(
                            f"[iter {iteration}] New coverage found — corpus size: {len(self.corpus.seeds())}"
                        )

                    iteration += 1

        except KeyboardInterrupt:
            print("\nFuzzing interrupted.")

        elapsed = time.monotonic() - start_time
        print(f"\nDone. {iteration} iterations in {elapsed:.1f}s.")
        print(
            f"Corpus size: {len(self.corpus.seeds())} | Crashes dir: {self.crashes_dir}"
        )
