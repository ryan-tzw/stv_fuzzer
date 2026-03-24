from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


@dataclass
class BlackboxObservation:
    behavior_signature: str
    crash_text: str
    exit_code: int | None
    timed_out: bool


class BlackboxObserver:
    def observe(
        self,
        process_result: dict,
        *,
        stdout: str = "",
        stderr: str = "",
        input_data: str = "",
    ) -> BlackboxObservation:
        combined = "\n".join(part for part in (stdout, stderr) if part)
        crash_text = _extract_traceback(combined)
        if process_result.get("timed_out"):
            timeout_s = process_result.get("duration_s", 0.0)
            crash_text = f"TimeoutError: target timed out after {timeout_s:.2f}s"

        behaviour_payload = {
            "exit_code": process_result.get("exit_code"),
            "timed_out": process_result.get("timed_out", False),
            "stdout": _normalise_output(stdout, input_data),
            "stderr": _normalise_output(stderr, input_data),
        }
        signature = hashlib.sha1(
            json.dumps(behaviour_payload, sort_keys=True).encode("utf-8")
        ).hexdigest()

        return BlackboxObservation(
            behavior_signature=signature,
            crash_text=crash_text,
            exit_code=process_result.get("exit_code"),
            timed_out=process_result.get("timed_out", False),
        )


def _normalise_output(output: str, input_data: str) -> str:
    if not output:
        return ""
    normalised = output.replace(input_data, "<INPUT>") if input_data else output
    return "\n".join(line.strip() for line in normalised.splitlines()).strip()


def _extract_traceback(combined: str) -> str:
    marker = "Traceback (most recent call last):"
    start = combined.rfind(marker)
    if start == -1:
        return ""

    lines = combined[start:].splitlines()
    captured: list[str] = []
    seen_frame = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if captured:
                break
            continue

        captured.append(line)
        if stripped.startswith("File "):
            seen_frame = True
            continue
        if stripped.startswith(marker):
            continue

        if seen_frame and not line.startswith(" "):
            break

    return "\n".join(captured).strip()
