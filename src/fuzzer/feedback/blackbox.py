from __future__ import annotations

from fuzzer.feedback.coverage import FeedbackResult
from fuzzer.observers.blackbox import BlackboxObservation


class BlackboxFeedback:
    def __init__(self) -> None:
        self._seen_behaviours: set[str] = set()

    def evaluate(
        self,
        signal: BlackboxObservation,
        stdout: str = "",
        stderr: str = "",
    ) -> FeedbackResult:
        del stdout, stderr
        add_to_corpus = signal.behavior_signature not in self._seen_behaviours
        if add_to_corpus:
            self._seen_behaviours.add(signal.behavior_signature)

        is_crash = signal.timed_out or bool(signal.crash_text)
        return FeedbackResult(
            add_to_corpus=add_to_corpus,
            is_crash=is_crash,
            crash_text=signal.crash_text,
        )
