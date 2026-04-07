"""
Fuzzing engine: orchestrates the main fuzzing loop.
"""

import time
from datetime import datetime, timezone

from fuzzer.assembly import EngineComponents, build_engine_components
from fuzzer.config import FuzzerConfig
from fuzzer.corpus import CorpusManager
from fuzzer.logger import FuzzerLogger
from fuzzer.observers import ObservationInput
from fuzzer.storage.database import FuzzerDatabase
from fuzzer.metrics import MetricsSnapshot
from fuzzer.metrics.graphs import (
    create_coverage_graph,
    create_unique_graph,
    create_interesting_graph,
)


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
        self.corpus = CorpusManager(
            config.corpus_dir,
            self.db,
            grammar_name=config.corpus,
        )
        runtime_components = components or build_engine_components(config)
        self.mutator = runtime_components.mutator
        self.scheduler = runtime_components.scheduler
        self.executor = runtime_components.executor
        self.observer = runtime_components.observer
        self.feedback = runtime_components.feedback
        self.crash_detector = runtime_components.crash_detector
        self.logger = FuzzerLogger(self.run_dir, config)

    def start(self) -> None:
        """Prepare engine resources, such as persistent executor startup."""
        try:
            self.executor.start()
        except AttributeError:
            pass

    def stop(self) -> None:
        """Clean up resources and persist current corpus state."""
        try:
            self.executor.stop()
        except AttributeError:
            pass

        self.db.flush_corpus(self.corpus.seeds())
        self.db.close()

    def __enter__(self) -> "FuzzingEngine":
        self.start()
        return self

    def __exit__(self, *args) -> None:
        self.stop()

    def _cycle_limit_reason(self, cycles: int) -> str | None:
        max_cycles = self.config.max_cycles
        if max_cycles is not None and cycles >= max_cycles:
            return f"reached max cycles ({max_cycles})"
        return None

    def _time_limit_reason(self, start_time: float) -> str | None:
        time_limit = self.config.time_limit
        if time_limit is not None:
            elapsed = time.monotonic() - start_time
            if elapsed >= time_limit:
                return f"reached time limit ({time_limit}s)"
        return None

    def _execute_once(
        self,
        *,
        seed,
        executions: int,
        cycle: int,
        unique_crashes: int,
        crashes: int,
        interesting_seed: int,
    ) -> tuple[int, int]:
        mutated = self.mutator.mutate(seed.data)
        run_result = self.executor.run(mutated)
        self.corpus.record_fuzzed(seed)

        signal = self.observer.observe(
            ObservationInput(
                stdout=run_result.stdout,
                stderr=run_result.stderr,
                exit_code=run_result.exit_code,
                result=run_result.result,
            )
        )
        add_to_corpus = self.feedback.evaluate(signal)
        is_crash = self.crash_detector.is_crash(
            exit_code=run_result.exit_code,
            stdout=run_result.stdout,
            stderr=run_result.stderr,
        )

        execution_id = executions + 1
        if is_crash:
            crashes += 1
            parsed_crash = getattr(signal, "parsed_crash", None)
            if parsed_crash is None:
                self.logger.log_stop_reason(
                    "warning: crash detected but observer produced no parsed crash"
                )
            else:
                is_new = self.db.record_crash(mutated, parsed_crash)
                if is_new:
                    unique_crashes += 1
                    self.logger.log_crash(execution_id, cycle, unique_crashes)
                else:
                    self.logger.log_duplicate_crash(execution_id, cycle)

        if add_to_corpus:
            _, added = self.corpus.add(mutated)

            if added:
                interesting_seed += 1
                self.logger.log_corpus_add(execution_id, cycle)

        executions = execution_id
        self.logger.tick(executions=executions, cycles=cycle)
        return executions, unique_crashes, crashes, interesting_seed

    def run(self) -> None:
        self.corpus.load()

        executions = 0
        cycles = 0
        unique_crashes = 0
        crashes = 0
        interesting_seed = 0
        start_time = time.monotonic()

        last_metrics_time = start_time
        last_execs = 0
        last_exec_time = start_time
        execs_per_sec = 0.0

        initial_metrics = MetricsSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            corpus_size=self.corpus.size(),
            interesting_seed=0,
            unique_crashes=unique_crashes,
            total_crashes=0,
            total_edges=self.feedback.total_edges(),
            executions=executions,
            execs_per_sec=0.0,
        )

        self.db.record_metrics(initial_metrics)

        with self.logger:
            self.logger.start(
                corpus_size=self.corpus.size(), executions=executions, cycles=cycles
            )

            try:
                self.start()
                while True:
                    stop_reason = self._cycle_limit_reason(cycles)
                    if stop_reason is not None:
                        self.logger.log_stop_reason(stop_reason)
                        break

                    active_cycle = cycles + 1
                    seed_index = 0
                    while seed_index < self.corpus.size():
                        stop_reason = self._time_limit_reason(start_time)
                        if stop_reason is not None:
                            self.logger.log_stop_reason(stop_reason)
                            break

                        seed = self.corpus.get(seed_index)
                        self.corpus.record_picked(seed)
                        energy = self.scheduler.energy(seed)

                        for _ in range(energy):
                            stop_reason = self._time_limit_reason(start_time)
                            if stop_reason is not None:
                                self.logger.log_stop_reason(stop_reason)
                                break

                            executions, unique_crashes, crashes, interesting_seed = (
                                self._execute_once(
                                    seed=seed,
                                    executions=executions,
                                    cycle=active_cycle,
                                    unique_crashes=unique_crashes,
                                    crashes=crashes,
                                    interesting_seed=interesting_seed,
                                )
                            )

                            now = time.monotonic()
                            if now - last_metrics_time >= 2.0:
                                delta_execs = executions - last_execs
                                delta_time = now - last_exec_time

                                execs_per_sec = (
                                    delta_execs / delta_time if delta_time > 0 else 0
                                )

                                last_execs = executions
                                last_exec_time = now

                                current_metrics = MetricsSnapshot(
                                    timestamp=datetime.now(timezone.utc).isoformat(),
                                    corpus_size=self.corpus.size(),
                                    interesting_seed=interesting_seed,
                                    unique_crashes=unique_crashes,
                                    total_crashes=crashes,
                                    total_edges=self.feedback.total_edges(),
                                    executions=executions,
                                    execs_per_sec=execs_per_sec,
                                )

                                self.db.record_metrics(current_metrics)
                                last_metrics_time = now

                        if stop_reason is not None:
                            break

                        seed_index += 1

                    if stop_reason is not None:
                        break

                    cycles = active_cycle
                    self.logger.tick(executions=executions, cycles=cycles)

                coverage_data = self.db.get_coverage_data()
                unique_data = self.db.get_unique_bugs_data()
                interesting_data = self.db.get_interesting_data()

                create_coverage_graph(coverage_data, self.run_dir)
                create_unique_graph(unique_data, self.run_dir)
                create_interesting_graph(interesting_data, self.run_dir)

            except KeyboardInterrupt:
                self.logger.log_stop_reason("interrupted by user")

            finally:
                print(self.db.display_metrics())
                self.stop()

        elapsed = time.monotonic() - start_time
        self.logger.print_summary(executions=executions, cycles=cycles, elapsed=elapsed)
