"""
In-process coverage runner shim.

Run as:
    python _inprocess_runner.py <harness_path> [harness_args...]

Reads input from stdin, runs the harness under in-memory coverage.py
(no .coverage file is written), and writes a single JSON line to stdout:

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

All harness-level stdout/stderr is captured and returned inside the JSON
payload so the executor can separate it from the coverage data cleanly.
"""

import io
import json
import runpy
import sys


def main() -> None:
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: _inprocess_runner.py <harness_path> [args...]\n")
        sys.exit(1)

    harness_path = sys.argv[1]

    # sys.argv seen by the harness: [harness_path, *extra_args]
    harness_argv = sys.argv[1:]

    # Read all stdin upfront so we can hand it to the harness.
    input_bytes = sys.stdin.buffer.read()

    # Keep a direct reference to the real stdout before we redirect.
    real_stdout = sys.__stdout__

    # ------------------------------------------------------------------ #
    #  Set up in-memory coverage — no data_file means nothing hits disk.  #
    # ------------------------------------------------------------------ #
    import coverage as coverage_module

    cov = coverage_module.Coverage(data_file=None, branch=True)

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
            import traceback

            captured_err.write(traceback.format_exc())
            exit_code = 1
        finally:
            cov.stop()
    finally:
        sys.argv = old_argv
        sys.stdin = old_stdin
        sys.stdout = old_stdout
        sys.stderr = old_stderr

    # ------------------------------------------------------------------ #
    #  Serialise coverage data                                            #
    # ------------------------------------------------------------------ #
    cov_data = cov.get_data()
    coverage_dict: dict = {}

    for file_path in cov_data.measured_files():
        lines = cov_data.lines(file_path)
        arcs = cov_data.arcs(file_path)
        coverage_dict[file_path] = {
            "lines": list(lines) if lines else [],
            "arcs": [list(a) for a in arcs] if arcs else [],
        }

    payload = {
        "stdout": captured_out.getvalue(),
        "stderr": captured_err.getvalue(),
        "exit_code": exit_code,
        "coverage": coverage_dict,
    }

    if real_stdout is not None:
        real_stdout.write(json.dumps(payload) + "\n")
        real_stdout.flush()
    else:
        sys.stderr.write("Error: no real stdout available to write coverage data\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
