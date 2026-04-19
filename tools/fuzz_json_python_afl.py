#!/usr/bin/env python3
"""python-afl harness for the json-decoder target.

This baseline uses stdlib ``json`` as the oracle and treats only meaningful
behavioral failures as crashes:

* PerformanceBug / InvalidityBug from buggy_json
* valid JSON rejected by buggy_json
* invalid JSON accepted by buggy_json
* semantic mismatch between stdlib json and buggy_json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import afl


_REPO_ROOT = Path(__file__).resolve().parents[1]
_TARGET_DIR = _REPO_ROOT / "targets" / "json-decoder"
if str(_TARGET_DIR) not in sys.path:
    sys.path.insert(0, str(_TARGET_DIR))

import buggy_json  # noqa: E402
from buggy_json.decoder_stv import InvalidityBug, JSONDecodeError, PerformanceBug  # noqa: E402


def _stable_json(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=True)


def main() -> int:
    # Start the fork server after imports but before reading the fuzz input.
    afl.init()

    if len(sys.argv) > 1 and sys.argv[1] != "-":
        data = Path(sys.argv[1]).read_bytes()
    else:
        data = sys.stdin.buffer.read()
    text = data.decode("utf-8", errors="ignore")

    try:
        expected = json.loads(text)
        expected_ok = True
    except Exception:
        expected = None
        expected_ok = False

    try:
        actual = buggy_json.loads(text)
        actual_ok = True
    except PerformanceBug:
        raise
    except InvalidityBug:
        raise
    except JSONDecodeError as exc:
        if expected_ok:
            raise RuntimeError(f"RejectedValidJson: {exc}") from exc
        return 0
    except Exception as exc:
        raise RuntimeError(f"UnexpectedException: {type(exc).__name__}: {exc}") from exc

    if not expected_ok and actual_ok:
        raise RuntimeError("AcceptedInvalidJson")

    if expected_ok and actual_ok:
        if _stable_json(expected) != _stable_json(actual):
            raise RuntimeError("SemanticMismatch")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
