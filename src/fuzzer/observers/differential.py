"""Observer for differential executor results.

Transforms raw :class:`DifferentialResult` into a structured signal that
feedback logic can consume (coverage + behavioral markers).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fuzzer.executors.base import ExecutionResult
from fuzzer.executors.coverage_exec.types import CoveragePayload
from fuzzer.executors.differential.composed import DifferentialResult
from fuzzer.observers.bug_category import parse_crash
from fuzzer.observers.input import ObservationInput, ParsedCrash
from fuzzer.observers.python_coverage import CoverageData, InProcessCoverageObserver


@dataclass(frozen=True)
class DifferentialSignal:
    """Structured signal derived from one differential execution."""

    whitebox_coverage: CoverageData
    blackbox_exit_code: int
    whitebox_exit_code: int
    blackbox_nonzero_exit: bool
    whitebox_nonzero_exit: bool
    exit_code_mismatch: bool
    blackbox_has_stderr: bool
    blackbox_has_traceback: bool
    parsed_crash: ParsedCrash


class DifferentialObserver:
    """Derive a typed differential signal from raw differential results."""

    def __init__(self, whitebox_project_dir: str | Path):
        self._coverage_observer = InProcessCoverageObserver(whitebox_project_dir)

    def observe(self, execution: ObservationInput) -> DifferentialSignal:
        """Build a DifferentialSignal from executor output."""
        result = self._as_differential_result(execution.result)
        coverage_payload = self._as_coverage_payload(result.whitebox.result)
        coverage = self._coverage_observer.observe_payload(coverage_payload)

        blackbox_exit = result.blackbox.exit_code
        whitebox_exit = result.whitebox.exit_code
        blackbox_stdout = result.blackbox.stdout or ""
        blackbox_stderr = result.blackbox.stderr or ""
        parsed_stderr = parse_crash(blackbox_stderr)
        parsed_stdout = parse_crash(blackbox_stdout)
        parsed_crash = self._ensure_parsed_crash(
            self._choose_best_parsed_crash(parsed_stderr, parsed_stdout),
            exit_code=blackbox_exit,
            stdout=blackbox_stdout,
            stderr=blackbox_stderr,
        )

        return DifferentialSignal(
            whitebox_coverage=coverage,
            blackbox_exit_code=blackbox_exit,
            whitebox_exit_code=whitebox_exit,
            blackbox_nonzero_exit=blackbox_exit != 0,
            whitebox_nonzero_exit=whitebox_exit != 0,
            exit_code_mismatch=blackbox_exit != whitebox_exit,
            blackbox_has_stderr=bool(blackbox_stderr.strip()),
            blackbox_has_traceback=("Traceback" in blackbox_stderr)
            or ("Traceback" in blackbox_stdout),
            parsed_crash=parsed_crash,
        )

    @classmethod
    def _choose_best_parsed_crash(
        cls, parsed_stderr: ParsedCrash, parsed_stdout: ParsedCrash
    ) -> ParsedCrash:
        """Choose the richer parsed crash metadata; ties prefer stderr."""
        stderr_score = cls._parsed_crash_quality_score(parsed_stderr)
        stdout_score = cls._parsed_crash_quality_score(parsed_stdout)
        if stderr_score >= stdout_score:
            return parsed_stderr
        return parsed_stdout

    @staticmethod
    def _parsed_crash_quality_score(parsed: ParsedCrash) -> int:
        score = 0
        if parsed.bug_category.strip().lower() != "unknown":
            score += 3
        if parsed.file != "unknown" and parsed.line != -1:
            score += 2
        if parsed.exception_type.strip():
            score += 1
        if parsed.exception_message.strip():
            score += 1
        if parsed.traceback.strip():
            score += 1
        return score

    @staticmethod
    def _ensure_parsed_crash(
        parsed: ParsedCrash,
        *,
        exit_code: int,
        stdout: str,
        stderr: str,
    ) -> ParsedCrash:
        has_type = bool(parsed.exception_type.strip())
        has_msg = bool(parsed.exception_message.strip())
        has_traceback = bool(parsed.traceback.strip())
        has_location = parsed.file != "unknown" or parsed.line != -1
        if has_type or has_msg or has_traceback or has_location:
            return parsed

        source_text = (stderr or stdout or "").strip()
        if len(source_text) > 240:
            source_text = source_text[:240] + "..."
        if not source_text:
            source_text = "<no stderr/stdout>"

        return ParsedCrash(
            exception_type="ExecutionCrash",
            exception_message=f"exit_code={exit_code}; output={source_text}",
            file="unknown",
            line=-1,
            traceback=stderr.strip() or source_text,
            bug_category="unknown",
            category_source="fallback_signal",
        )

    @staticmethod
    def _as_coverage_payload(value: Any) -> CoveragePayload:
        if not isinstance(value, dict):
            raise TypeError(
                "differential observer expected whitebox coverage payload to be dict, "
                f"got {type(value).__name__}"
            )
        return value

    @staticmethod
    def _as_differential_result(value: Any) -> DifferentialResult:
        if not isinstance(value, DifferentialResult):
            raise TypeError(
                "differential observer expected DifferentialResult, "
                f"got {type(value).__name__}"
            )
        if not isinstance(value.blackbox, ExecutionResult):
            raise TypeError(
                "differential observer expected DifferentialResult.blackbox to be "
                f"ExecutionResult, got {type(value.blackbox).__name__}"
            )
        if not isinstance(value.whitebox, ExecutionResult):
            raise TypeError(
                "differential observer expected DifferentialResult.whitebox to be "
                f"ExecutionResult, got {type(value.whitebox).__name__}"
            )
        return value
