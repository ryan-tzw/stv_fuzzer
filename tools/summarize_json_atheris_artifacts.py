#!/usr/bin/env python3
"""Summarize Atheris artifact files for the local json-decoder target."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]
_TARGET_DIR = _REPO_ROOT / "targets" / "json-decoder"
if str(_TARGET_DIR) not in sys.path:
    sys.path.insert(0, str(_TARGET_DIR))

import buggy_json  # noqa: E402
from buggy_json.decoder_stv import InvalidityBug, JSONDecodeError, PerformanceBug  # noqa: E402


def _stable_json(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=True)


def _classify(path: Path) -> str:
    text = path.read_bytes().decode("utf-8", errors="ignore")

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
        return "PerformanceBug"
    except InvalidityBug:
        return "InvalidityBug"
    except JSONDecodeError:
        actual = None
        actual_ok = False
    except Exception as exc:
        return f"Unexpected:{type(exc).__name__}"

    if expected_ok and not actual_ok:
        return "RejectedValidJson"
    if not expected_ok and actual_ok:
        return "AcceptedInvalidJson"
    if expected_ok and actual_ok and _stable_json(expected) != _stable_json(actual):
        return "SemanticMismatch"
    if not expected_ok and not actual_ok:
        return "BothRejected"
    return "NoIssue"


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python tools/summarize_json_atheris_artifacts.py <artifact_dir>")
        return 1

    artifact_dir = Path(sys.argv[1]).resolve()
    files = sorted(
        path
        for path in artifact_dir.iterdir()
        if path.is_file() and path.suffix != ".json"
    )
    counts: Counter[str] = Counter()

    for path in files:
        counts[_classify(path)] += 1

    print(f"artifact_dir: {artifact_dir}")
    print(f"artifacts: {len(files)}")
    for label, count in sorted(counts.items()):
        print(f"{label}: {count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
