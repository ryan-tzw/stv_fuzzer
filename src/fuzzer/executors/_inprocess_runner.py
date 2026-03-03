"""
In-process coverage runner shim.

Single-shot mode (default)::

    python _inprocess_runner.py <harness_path> [harness_args...]

    Reads a fuzz input from stdin, runs the harness once, writes one JSON
    line to stdout, then exits.

Persistent (loop) mode::

    python _inprocess_runner.py --loop <harness_path> [harness_args...]

    Stays alive and processes requests indefinitely.  Each request is a
    JSON line read from stdin; each response is a JSON line written to
    stdout.  The loop ends on stdin EOF or when a request contains
    ``{"cmd": "exit"}``.

    Request schema:  {"input": "<fuzz input string or null>"}
    Response schema: see below.

Response schema (both modes)::

    {
        "stdout":    "<captured harness stdout>",
        "stderr":    "<captured harness stderr>",
        "exit_code": <int>,
        "coverage":  {
            "<abs_file_path>": {
                "lines": [int, ...],
                "arcs":  [[int, int], ...]
            },
            ...
        }
    }

In loop mode the target module and its dependencies remain in
``sys.modules`` across iterations (intentional — avoids repeated import
overhead).  Coverage is measured afresh for each run via a new
``Coverage`` instance, so per-iteration signals remain accurate.
"""

import io
import json
import runpy
import sys
import traceback

import coverage as _coverage_module

# --------------------------------------------------------------------------- #
#  Core: run the harness once and return a payload dict                       #
# --------------------------------------------------------------------------- #


def _run_once(harness_path: str, harness_argv: list, input_str: str | None) -> dict:
    """
    Run *harness_path* under a fresh in-memory coverage instance.

    *harness_argv* becomes ``sys.argv`` inside the harness.
    *input_str* (or an empty string if ``None``) is fed to the harness
    via a redirected ``sys.stdin``.

    Returns the JSON-serialisable payload dict.
    """
    input_bytes = (input_str or "").encode()

    cov = _coverage_module.Coverage(data_file=None, branch=True)

    captured_out = io.StringIO()
    captured_err = io.StringIO()
    exit_code: int = 0

    old_argv = sys.argv
    old_stdin = sys.stdin
    old_stdout = sys.stdout
    old_stderr = sys.stderr

    try:
        sys.argv = harness_argv
        sys.stdin = io.TextIOWrapper(io.BytesIO(input_bytes))
        sys.stdout = captured_out
        sys.stderr = captured_err

        cov.start()
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
            cov.stop()
    finally:
        sys.argv = old_argv
        sys.stdin = old_stdin
        sys.stdout = old_stdout
        sys.stderr = old_stderr

    cov_data = cov.get_data()
    coverage_dict: dict = {}
    for file_path in cov_data.measured_files():
        lines = cov_data.lines(file_path)
        arcs = cov_data.arcs(file_path)
        coverage_dict[file_path] = {
            "lines": list(lines) if lines else [],
            "arcs": [list(a) for a in arcs] if arcs else [],
        }

    return {
        "stdout": captured_out.getvalue(),
        "stderr": captured_err.getvalue(),
        "exit_code": exit_code,
        "coverage": coverage_dict,
    }


# --------------------------------------------------------------------------- #
#  Modes                                                                      #
# --------------------------------------------------------------------------- #


def _single_shot(harness_path: str, harness_argv: list) -> None:
    """Read stdin once, run the harness once, write one JSON line, exit."""
    real_stdout = sys.__stdout__
    input_str = sys.stdin.read()  # read before any redirection
    payload = _run_once(harness_path, harness_argv, input_str)
    if real_stdout is None:
        sys.stderr.write("Error: no real stdout available\n")
        sys.exit(1)
    real_stdout.write(json.dumps(payload) + "\n")
    real_stdout.flush()


def _loop(harness_path: str, harness_argv: list) -> None:
    """
    Persistent request/response loop.

    Reads JSON request lines from the *real* stdin (the pipe from the
    executor) and writes JSON response lines to the *real* stdout.  The
    real streams are captured before the loop so that harness-level
    redirections cannot corrupt the protocol channel.
    """
    real_stdin = sys.__stdin__
    real_stdout = sys.__stdout__

    if real_stdin is None or real_stdout is None:
        sys.stderr.write("Error: real stdin/stdout not available for loop mode\n")
        sys.exit(1)

    while True:
        line = real_stdin.readline()
        if not line:  # EOF — executor closed the pipe
            break

        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue  # malformed line; skip silently

        if request.get("cmd") == "exit":
            break

        payload = _run_once(harness_path, harness_argv, request.get("input"))
        real_stdout.write(json.dumps(payload) + "\n")
        real_stdout.flush()


def main() -> None:
    # Strip --loop flag before any other arg processing.
    loop_mode = len(sys.argv) > 1 and sys.argv[1] == "--loop"
    if loop_mode:
        sys.argv.pop(1)

    if len(sys.argv) < 2:
        sys.stderr.write(
            "Usage: _inprocess_runner.py [--loop] <harness_path> [args...]\n"
        )
        sys.exit(1)

    harness_path = sys.argv[1]
    harness_argv = sys.argv[1:]  # [harness_path, *extra_args]

    if loop_mode:
        _loop(harness_path, harness_argv)
    else:
        _single_shot(harness_path, harness_argv)


if __name__ == "__main__":
    main()
