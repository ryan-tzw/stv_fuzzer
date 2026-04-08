def _make_input(*, stdout: str, stderr: str):
    from fuzzer.executors.base import ExecutionResult
    from fuzzer.executors.differential.composed import DifferentialResult
    from fuzzer.observers.input import ObservationInput

    blackbox = ExecutionResult(
        stdout=stdout,
        stderr=stderr,
        exit_code=1,
        result={},
    )
    whitebox = ExecutionResult(
        stdout="",
        stderr="",
        exit_code=0,
        result={},
    )
    return ObservationInput(
        stdout=stdout,
        stderr=stderr,
        exit_code=1,
        result=DifferentialResult(blackbox=blackbox, whitebox=whitebox),
    )


def _ensure(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    from pathlib import Path

    from fuzzer.observers.differential import DifferentialObserver

    observer = DifferentialObserver(whitebox_project_dir=Path.cwd())

    # 1) stderr empty + stdout rich -> stdout parse should win.
    rich_stdout = (
        "An invalidity bug has been triggered: Expecting value\n"
        "============================================================\n"
        "TRACEBACK\n"
        "============================================================\n"
        "Traceback (most recent call last):\n"
        '  File "buggy_json/decoder_stv.py", line 384, in raw_decode\n'
        "buggy_json.decoder_stv.JSONDecodeError: Expecting value"
    )
    signal = observer.observe(_make_input(stdout=rich_stdout, stderr=""))
    _ensure(
        signal.parsed_crash.bug_category == "invalidity",
        "stdout-rich parse should classify as invalidity",
    )
    _ensure(
        signal.parsed_crash.file == "buggy_json/decoder_stv.py",
        "stdout-rich parse should capture file location",
    )

    # 2) stderr richer than stdout -> stderr should win.
    weak_stdout = "oops"
    rich_stderr = rich_stdout.replace("invalidity", "functional")
    signal = observer.observe(_make_input(stdout=weak_stdout, stderr=rich_stderr))
    _ensure(
        signal.parsed_crash.bug_category == "functional",
        "stderr-rich parse should be preferred over weak stdout",
    )

    # 3) tie quality -> stderr should win.
    tie_stdout = "ValueError: from stdout"
    tie_stderr = "RuntimeError: from stderr"
    signal = observer.observe(_make_input(stdout=tie_stdout, stderr=tie_stderr))
    _ensure(
        signal.parsed_crash.exception_type == "RuntimeError",
        "tie should prefer stderr parse",
    )

    # 4) both weak/empty -> fallback_signal should still provide structured crash.
    signal = observer.observe(_make_input(stdout="", stderr=""))
    _ensure(
        signal.parsed_crash.category_source == "fallback_signal",
        "empty streams should fall back to fallback_signal",
    )
    _ensure(
        bool(signal.parsed_crash.exception_type.strip()),
        "fallback should include non-empty exception_type",
    )
    _ensure(
        bool(signal.parsed_crash.exception_message.strip()),
        "fallback should include non-empty exception_message",
    )

    # 5) traceback in stdout only should set blackbox_has_traceback.
    stdout_only_traceback = "Traceback (most recent call last):\nValueError: boom"
    signal = observer.observe(_make_input(stdout=stdout_only_traceback, stderr=""))
    _ensure(
        signal.blackbox_has_traceback,
        "traceback marker in stdout should set blackbox_has_traceback=True",
    )

    print("smoke_differential_observer: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
