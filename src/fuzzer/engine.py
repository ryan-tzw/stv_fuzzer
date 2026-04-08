"""
Fuzzing engine: orchestrates the main fuzzing loop.
"""

import time
from datetime import datetime
from typing import Any

from fuzzer.assembly import EngineComponents, build_engine_components
from fuzzer.config import FuzzerConfig
from fuzzer.contracts import (
    CoverageStatsProvider,
    CrashSignalProtocol,
    SupportsCycleStart,
)
from fuzzer.corpus import CorpusManager
from fuzzer.logger import FuzzerLogger
from fuzzer.metrics import TelemetryRecorder
from fuzzer.observers import ObservationInput
from fuzzer.storage.database import FuzzerDatabase


class FuzzingEngine:
    _METRICS_SNAPSHOT_INTERVAL_S = 2.0

    def __init__(
        self, config: FuzzerConfig, components: EngineComponents[Any] | None = None
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
        self.executor.start()

    def stop(self) -> None:
        """Clean up resources and persist current corpus state."""
        stop_error: BaseException | None = None
        flush_error: BaseException | None = None
        try:
            self.executor.stop()
        except BaseException as exc:
            stop_error = exc

        try:
            self.db.flush_corpus(self.corpus.seeds())
        except BaseException as exc:
            flush_error = exc
        finally:
            self.db.close()

        if stop_error is not None:
            if flush_error is not None:
                stop_error.add_note(
                    f"database flush also failed during stop cleanup: {flush_error!r}"
                )
            raise stop_error
        if flush_error is not None:
            raise flush_error

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

    def _notify_feedback_cycle_start(self, cycle: int) -> None:
        """Notify feedback of cycle boundary when supported."""
        if isinstance(self.feedback, SupportsCycleStart):
            self.feedback.on_cycle_start(cycle)

    def _coverage_counts(self) -> tuple[int, int, int]:
        """Return cumulative unique line/branch/arc counts from active feedback."""
        if not isinstance(self.feedback, CoverageStatsProvider):
            return 0, 0, 0

        line_coverage = self.feedback.total_seen_lines
        branch_coverage = self.feedback.total_seen_branches
        arc_coverage = self.feedback.total_seen_arcs
        return (
            line_coverage if isinstance(line_coverage, int) else 0,
            branch_coverage if isinstance(branch_coverage, int) else 0,
            arc_coverage if isinstance(arc_coverage, int) else 0,
        )

    def _execute_once(
        self,
        *,
        seed,
        executions: int,
        cycle: int,
        unique_crashes: int,
    ) -> tuple[int, int, int, int, int, bool, bool]:
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
            parsed_crash = (
                signal.parsed_crash if isinstance(signal, CrashSignalProtocol) else None
            )
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
            corpus_size_before = self.corpus.size()
            self.corpus.add(mutated)
            added_to_corpus = self.corpus.size() > corpus_size_before
            if added_to_corpus:
                self.logger.log_corpus_add(execution_id, cycle)
        else:
            added_to_corpus = False

        executions = execution_id
        line_coverage, branch_coverage, arc_coverage = self._coverage_counts()
        self.logger.tick(
            executions=executions,
            cycles=cycle,
            line_coverage=line_coverage,
            branch_coverage=branch_coverage,
            arc_coverage=arc_coverage,
        )
        return (
            executions,
            unique_crashes,
            line_coverage,
            branch_coverage,
            arc_coverage,
            is_crash,
            added_to_corpus,
        )

    def run(self) -> None:
        self.corpus.load()

        executions = 0
        cycles = 0
        unique_crashes = 0
        total_crashes = 0
        interesting_seed = 0
        line_coverage, branch_coverage, arc_coverage = self._coverage_counts()
        start_time = time.monotonic()
        telemetry = TelemetryRecorder(
            self.db,
            interval_s=self._METRICS_SNAPSHOT_INTERVAL_S,
        )

        with self.logger:
            self.logger.start(
                corpus_size=self.corpus.size(),
                executions=executions,
                cycles=cycles,
                line_coverage=line_coverage,
                branch_coverage=branch_coverage,
                arc_coverage=arc_coverage,
            )

            run_error: BaseException | None = None
            try:
                warning = telemetry.start(
                    now=start_time,
                    corpus_size=self.corpus.size(),
                    interesting_seed=interesting_seed,
                    unique_crashes=unique_crashes,
                    total_crashes=total_crashes,
                    total_edges=arc_coverage,
                    executions=executions,
                )
                if warning is not None:
                    self.logger.log_stop_reason(warning)

                self.start()
                while True:
                    stop_reason = self._cycle_limit_reason(cycles)
                    if stop_reason is not None:
                        self.logger.log_stop_reason(stop_reason)
                        break

                    active_cycle = cycles + 1
                    self._notify_feedback_cycle_start(active_cycle)
                    cycle_pool = self.corpus.seeds()
                    cycle_budget = len(cycle_pool)
                    for _ in range(cycle_budget):
                        stop_reason = self._time_limit_reason(start_time)
                        if stop_reason is not None:
                            self.logger.log_stop_reason(stop_reason)
                            break

                        seed = self.scheduler.next(cycle_pool)
                        self.corpus.record_picked(seed)
                        energy = self.scheduler.energy(seed)

                        for _ in range(energy):
                            stop_reason = self._time_limit_reason(start_time)
                            if stop_reason is not None:
                                self.logger.log_stop_reason(stop_reason)
                                break

                            (
                                executions,
                                unique_crashes,
                                line_coverage,
                                branch_coverage,
                                arc_coverage,
                                is_crash,
                                added_to_corpus,
                            ) = self._execute_once(
                                seed=seed,
                                executions=executions,
                                cycle=active_cycle,
                                unique_crashes=unique_crashes,
                            )
                            if is_crash:
                                total_crashes += 1
                            if added_to_corpus:
                                interesting_seed += 1

                            warning = telemetry.maybe_record(
                                now=time.monotonic(),
                                corpus_size=self.corpus.size(),
                                interesting_seed=interesting_seed,
                                unique_crashes=unique_crashes,
                                total_crashes=total_crashes,
                                total_edges=arc_coverage,
                                executions=executions,
                            )
                            if warning is not None:
                                self.logger.log_stop_reason(warning)

                        if stop_reason is not None:
                            break

                    if stop_reason is not None:
                        break

                    cycles = active_cycle
                    self.logger.tick(
                        executions=executions,
                        cycles=cycles,
                        line_coverage=line_coverage,
                        branch_coverage=branch_coverage,
                        arc_coverage=arc_coverage,
                    )

            except KeyboardInterrupt:
                self.logger.log_stop_reason("interrupted by user")
            except BaseException as exc:
                run_error = exc

            finally:
                warning = telemetry.finalize(
                    now=time.monotonic(),
                    corpus_size=self.corpus.size(),
                    interesting_seed=interesting_seed,
                    unique_crashes=unique_crashes,
                    total_crashes=total_crashes,
                    total_edges=arc_coverage,
                    executions=executions,
                )
                if warning is not None:
                    self.logger.log_stop_reason(warning)

                try:
                    self.stop()
                except BaseException as stop_exc:
                    if run_error is None:
                        raise
                    run_error.add_note(f"engine stop cleanup also failed: {stop_exc!r}")

            if run_error is not None:
                raise run_error

        elapsed = time.monotonic() - start_time
        self.logger.print_summary(executions=executions, cycles=cycles, elapsed=elapsed)
