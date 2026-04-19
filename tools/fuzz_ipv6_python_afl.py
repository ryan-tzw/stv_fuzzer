#!/usr/bin/env python3
"""python-afl harness for the IPv6 parser target (``ipyparse.ipv6``).

Oracle: Python stdlib ``ipaddress.IPv6Address`` vs ``ipyparse``. A crash is
only signalled for meaningful divergences:

* valid IPv6 rejected by ipyparse
* invalid IPv6 accepted by ipyparse
* semantic mismatch (different integer values)
* unexpected exception type (anything outside ``ParseException``)
"""

from __future__ import annotations

import ipaddress
import sys
from pathlib import Path

import afl
import ipyparse

# ipyparse.ipv6 expects a sibling module name ``ipparse`` on sys.modules;
# the main fuzzer uses the same 2-line alias shim.
sys.modules.setdefault("ipparse", ipyparse)

from ipyparse.ipv6 import IPv6_WholeString  # noqa: E402
from pyparsing import ParseException  # noqa: E402


def main() -> int:
    # Start the fork server after imports but before reading the fuzz input.
    afl.init()

    if len(sys.argv) > 1 and sys.argv[1] != "-":
        data = Path(sys.argv[1]).read_bytes()
    else:
        data = sys.stdin.buffer.read()
    text = data.decode("utf-8", errors="ignore")

    try:
        expected = int(ipaddress.IPv6Address(text))
        expected_ok = True
    except ipaddress.AddressValueError:
        expected = None
        expected_ok = False
    except ValueError:
        expected = None
        expected_ok = False

    try:
        actual = IPv6_WholeString.parse_string(text, parse_all=True)[0]
        actual_ok = True
    except ParseException:
        actual = None
        actual_ok = False
    except Exception as exc:
        raise RuntimeError(f"UnexpectedException: {type(exc).__name__}: {exc}") from exc

    if expected_ok and not actual_ok:
        raise RuntimeError(f"RejectedValidIPv6: {text!r}")
    if not expected_ok and actual_ok:
        raise RuntimeError(f"AcceptedInvalidIPv6: {text!r}")
    if expected_ok and actual_ok and actual != expected:
        raise RuntimeError(
            f"SemanticMismatchIPv6: text={text!r} expected={expected} actual={actual}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
