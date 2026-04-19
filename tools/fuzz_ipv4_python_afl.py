#!/usr/bin/env python3
"""python-afl harness for the IPv4 parser target (``ipyparse.ipv4.IPv4``).

Oracle: Python stdlib ``ipaddress.IPv4Address`` vs ``ipyparse``. A crash is
only signalled for meaningful divergences:

* valid IPv4 rejected by ipyparse
* invalid IPv4 accepted by ipyparse
* semantic mismatch (different integer values)
* unexpected exception type (anything outside ``ParseException``)
"""

from __future__ import annotations

import ipaddress
import sys
from pathlib import Path

import afl
from ipyparse.ipv4 import IPv4
from pyparsing import ParseException


def main() -> int:
    # Start the fork server after imports but before reading the fuzz input.
    afl.init()

    if len(sys.argv) > 1 and sys.argv[1] != "-":
        data = Path(sys.argv[1]).read_bytes()
    else:
        data = sys.stdin.buffer.read()
    text = data.decode("utf-8", errors="ignore")

    try:
        expected = int(ipaddress.IPv4Address(text))
        expected_ok = True
    except ipaddress.AddressValueError:
        expected = None
        expected_ok = False
    except ValueError:
        expected = None
        expected_ok = False

    try:
        actual = IPv4.parse_string(text, parse_all=True)[0]
        actual_ok = True
    except ParseException:
        actual = None
        actual_ok = False
    except Exception as exc:
        raise RuntimeError(f"UnexpectedException: {type(exc).__name__}: {exc}") from exc

    if expected_ok and not actual_ok:
        raise RuntimeError(f"RejectedValidIPv4: {text!r}")
    if not expected_ok and actual_ok:
        raise RuntimeError(f"AcceptedInvalidIPv4: {text!r}")
    if expected_ok and actual_ok and actual != expected:
        raise RuntimeError(
            f"SemanticMismatchIPv4: text={text!r} expected={expected} actual={actual}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
