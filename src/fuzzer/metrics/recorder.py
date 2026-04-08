"""Telemetry snapshot recording helper for fuzz runs."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from fuzzer.metrics.metrics import MetricsSnapshot

if TYPE_CHECKING:
    from fuzzer.storage.database import FuzzerDatabase


class TelemetryRecorder:
    """Manage periodic + final metrics snapshots for one fuzzing run."""

    def __init__(self, db: "FuzzerDatabase", *, interval_s: float = 2.0) -> None:
        if interval_s <= 0:
            raise ValueError("interval_s must be > 0")
        self._db = db
        self._interval_s = interval_s
        self._last_snapshot_time: float | None = None
        self._last_exec_checkpoint = 0
        self._last_exec_checkpoint_time: float | None = None
        self._reported_write_error = False

    def start(
        self,
        *,
        now: float,
        corpus_size: int,
        interesting_seed: int,
        unique_crashes: int,
        total_crashes: int,
        line_coverage: int,
        branch_coverage: int,
        total_edges: int,
        executions: int,
    ) -> str | None:
        self._last_snapshot_time = now
        self._last_exec_checkpoint = executions
        self._last_exec_checkpoint_time = now
        return self._record(
            corpus_size=corpus_size,
            interesting_seed=interesting_seed,
            unique_crashes=unique_crashes,
            total_crashes=total_crashes,
            line_coverage=line_coverage,
            branch_coverage=branch_coverage,
            total_edges=total_edges,
            executions=executions,
            execs_per_sec=0.0,
        )

    def maybe_record(
        self,
        *,
        now: float,
        corpus_size: int,
        interesting_seed: int,
        unique_crashes: int,
        total_crashes: int,
        line_coverage: int,
        branch_coverage: int,
        total_edges: int,
        executions: int,
    ) -> str | None:
        if self._last_snapshot_time is None or self._last_exec_checkpoint_time is None:
            return None
        if now - self._last_snapshot_time < self._interval_s:
            return None

        delta_execs = executions - self._last_exec_checkpoint
        delta_time = now - self._last_exec_checkpoint_time
        execs_per_sec = delta_execs / delta_time if delta_time > 0 else 0.0
        warning = self._record(
            corpus_size=corpus_size,
            interesting_seed=interesting_seed,
            unique_crashes=unique_crashes,
            total_crashes=total_crashes,
            line_coverage=line_coverage,
            branch_coverage=branch_coverage,
            total_edges=total_edges,
            executions=executions,
            execs_per_sec=execs_per_sec,
        )
        self._last_snapshot_time = now
        self._last_exec_checkpoint = executions
        self._last_exec_checkpoint_time = now
        return warning

    def finalize(
        self,
        *,
        now: float,
        corpus_size: int,
        interesting_seed: int,
        unique_crashes: int,
        total_crashes: int,
        line_coverage: int,
        branch_coverage: int,
        total_edges: int,
        executions: int,
    ) -> str | None:
        if self._last_exec_checkpoint_time is None:
            execs_per_sec = 0.0
        else:
            elapsed = now - self._last_exec_checkpoint_time
            execs_per_sec = (
                (executions - self._last_exec_checkpoint) / elapsed
                if elapsed > 0
                else 0.0
            )
        return self._record(
            corpus_size=corpus_size,
            interesting_seed=interesting_seed,
            unique_crashes=unique_crashes,
            total_crashes=total_crashes,
            line_coverage=line_coverage,
            branch_coverage=branch_coverage,
            total_edges=total_edges,
            executions=executions,
            execs_per_sec=execs_per_sec,
        )

    def _record(
        self,
        *,
        corpus_size: int,
        interesting_seed: int,
        unique_crashes: int,
        total_crashes: int,
        line_coverage: int,
        branch_coverage: int,
        total_edges: int,
        executions: int,
        execs_per_sec: float,
    ) -> str | None:
        snapshot = MetricsSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            corpus_size=corpus_size,
            interesting_seed=interesting_seed,
            unique_crashes=unique_crashes,
            total_crashes=total_crashes,
            line_coverage=line_coverage,
            branch_coverage=branch_coverage,
            total_edges=total_edges,
            executions=executions,
            execs_per_sec=execs_per_sec,
        )
        try:
            self._db.record_metrics(snapshot)
        except BaseException as exc:
            if self._reported_write_error:
                return None
            self._reported_write_error = True
            return f"warning: failed to record telemetry snapshot: {exc!r}"
        return None
