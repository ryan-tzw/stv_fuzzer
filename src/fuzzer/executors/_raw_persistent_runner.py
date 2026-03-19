"""Runner shim for raw (non-coverage) persistent execution.

Works in single-shot or ``--loop`` mode, communicating JSON over stdin/stdout.
The output is a dict with keys ``stdout``, ``stderr`` and ``exit_code``.
"""

import io
import json
import runpy
import sys
import traceback


def _run_once(
    harness_path: str, harness_argv: list[str], input_str: str | None
) -> dict:
    """Run *harness_path* once and return a JSON-serialisable payload."""
    input_bytes = (input_str or "").encode()

    captured_out = io.StringIO()
    captured_err = io.StringIO()
    exit_code = 0

    old_argv = sys.argv
    old_stdin = sys.stdin
    old_stdout = sys.stdout
    old_stderr = sys.stderr

    try:
        sys.argv = harness_argv
        sys.stdin = io.TextIOWrapper(io.BytesIO(input_bytes))
        sys.stdout = captured_out
        sys.stderr = captured_err

        try:
            runpy.run_path(harness_path, run_name="__main__")
        except SystemExit as exc:
            if isinstance(exc.code, int):
                exit_code = exc.code
            elif exc.code is None:
                exit_code = 0
            else:
                exit_code = 1
        except Exception:
            captured_err.write(traceback.format_exc())
            exit_code = 1
    finally:
        sys.argv = old_argv
        sys.stdin = old_stdin
        sys.stdout = old_stdout
        sys.stderr = old_stderr

    return {
        "stdout": captured_out.getvalue(),
        "stderr": captured_err.getvalue(),
        "exit_code": exit_code,
    }


def _single_shot(harness_path: str, harness_argv: list[str]) -> None:
    """Read stdin once, run once, write one JSON line, exit."""
    real_stdout = sys.__stdout__
    input_str = sys.stdin.read()
    payload = _run_once(harness_path, harness_argv, input_str)
    if real_stdout is None:
        sys.stderr.write("Error: no real stdout available\n")
        sys.exit(1)
    real_stdout.write(json.dumps(payload) + "\n")
    real_stdout.flush()


def _loop(harness_path: str, harness_argv: list[str]) -> None:
    """Persistent request/response loop using NDJSON on stdin/stdout."""
    real_stdin = sys.__stdin__
    real_stdout = sys.__stdout__

    if real_stdin is None or real_stdout is None:
        sys.stderr.write("Error: real stdin/stdout not available for loop mode\n")
        sys.exit(1)

    while True:
        line = real_stdin.readline()
        if not line:
            break

        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue

        if request.get("cmd") == "exit":
            break

        payload = _run_once(harness_path, harness_argv, request.get("input"))
        real_stdout.write(json.dumps(payload) + "\n")
        real_stdout.flush()


def main() -> None:
    loop_mode = len(sys.argv) > 1 and sys.argv[1] == "--loop"
    if loop_mode:
        sys.argv.pop(1)

    if len(sys.argv) < 2:
        sys.stderr.write(
            "Usage: _raw_persistent_runner.py [--loop] <harness_path> [args...]\n"
        )
        sys.exit(1)

    harness_path = sys.argv[1]
    harness_argv = sys.argv[1:]

    if loop_mode:
        _loop(harness_path, harness_argv)
    else:
        _single_shot(harness_path, harness_argv)


if __name__ == "__main__":
    main()
