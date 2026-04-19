#!/usr/bin/env python3
"""python-afl harness for ``cidrize.cidrize`` (IPv4-shaped inputs).

``cidrize`` has no safe external oracle for ranges/wildcards, so the
harness uses a **self-consistency + round-trip** oracle:

1. Call ``cidrize(s)`` — on success we get a list of ``IPNetwork``.
2. For each ``IPNetwork`` returned, ``str(net)`` → re-parse with
   ``cidrize`` and expect the same network set.

A labeled ``RuntimeError`` is raised on:

* unexpected exception type (anything outside ``CidrizeError`` / ``ValueError``)
* round-trip mismatch
* ``signal.alarm``-triggered hang (``PerformanceBug``)

Labels line up with ``summarize_python_afl_artifacts.py`` so crash
classification is consistent.
"""

from __future__ import annotations

import signal
import sys
from pathlib import Path

import afl
import cidrize


class PerformanceBug(RuntimeError):
    pass


def _install_timeout(seconds: int) -> None:
    def _handler(signum, frame):  # noqa: ANN001
        raise PerformanceBug(f"cidrize exceeded {seconds}s")

    signal.signal(signal.SIGALRM, _handler)
    signal.alarm(seconds)


def _clear_timeout() -> None:
    signal.alarm(0)


def main() -> int:
    # Start the fork server after imports but before reading the fuzz input.
    afl.init()

    if len(sys.argv) > 1 and sys.argv[1] != "-":
        data = Path(sys.argv[1]).read_bytes()
    else:
        data = sys.stdin.buffer.read()
    text = data.decode("utf-8", errors="ignore")

    _install_timeout(10)
    try:
        try:
            first = cidrize.cidrize(text, raise_errors=True)
        except PerformanceBug:
            raise
        except cidrize.CidrizeError:
            return 0
        except ValueError:
            return 0
        except Exception as exc:
            raise RuntimeError(
                f"UnexpectedException: {type(exc).__name__}: {exc}"
            ) from exc

        first_keys = sorted(str(n) for n in first)

        try:
            second_nets: list = []
            for rt in first_keys:
                second_nets.extend(cidrize.cidrize(rt, raise_errors=True))
        except PerformanceBug:
            raise
        except Exception as exc:
            raise RuntimeError(
                f"RoundTripMismatch: reparse failed: {type(exc).__name__}: {exc}"
            ) from exc

        second_keys = sorted(str(n) for n in second_nets)
        if first_keys != second_keys:
            raise RuntimeError(
                f"RoundTripMismatch: first={first_keys} second={second_keys}"
            )
    finally:
        _clear_timeout()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
