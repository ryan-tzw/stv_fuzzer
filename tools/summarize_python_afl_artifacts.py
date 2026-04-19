#!/usr/bin/env python3
"""Summarize python-afl ``crashes/`` for a given target.

AFL writes crash files with names like ``id:000001,sig:06,src:000123+000045``
(not a JSON suffix like Atheris), so we enumerate by the ``id:`` prefix.

Per target, the classifier mirrors the harness oracle labels so bugs
found by python-afl get the same labels that ``fuzz_<t>_python_afl.py``
would raise, enabling direct cross-baseline comparison with Atheris.

Writes ``summary.json`` next to the crashes dir with per-label counts and
(label, exception_type, file, line) dedup keys.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import signal
import sys
from collections import Counter, defaultdict
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TARGET_DIR_JSON = _REPO_ROOT / "targets" / "json-decoder"
if str(_TARGET_DIR_JSON) not in sys.path:
    sys.path.insert(0, str(_TARGET_DIR_JSON))

# JSON classifier reused verbatim from the Atheris tool for cross-baseline parity.
_TOOLS_DIR = _REPO_ROOT / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))
from summarize_json_atheris_artifacts import _classify as _classify_json  # noqa: E402


def _decode(path: Path) -> str:
    return path.read_bytes().decode("utf-8", errors="ignore")


def _classify_ipv4(path: Path) -> str:
    text = _decode(path)
    try:
        from ipyparse.ipv4 import IPv4
    except ImportError as exc:
        return f"EnvError:{type(exc).__name__}"

    try:
        ref_value: int | None = int(ipaddress.IPv4Address(text))
        ref_ok = True
    except ipaddress.AddressValueError:
        ref_value = None
        ref_ok = False
    except ValueError:
        ref_value = None
        ref_ok = False

    try:
        sut_value = IPv4.parse_string(text, parse_all=True)[0]
        sut_ok = True
    except Exception as exc:
        sut_value = None
        sut_ok = False
        sut_err_name = type(exc).__name__
        if "ParseException" not in sut_err_name:
            return f"UnexpectedException:{sut_err_name}"

    if ref_ok and not sut_ok:
        return "RejectedValidIPv4"
    if not ref_ok and sut_ok:
        return "AcceptedInvalidIPv4"
    if ref_ok and sut_ok and sut_value != ref_value:
        return "SemanticMismatchIPv4"
    return "NoIssue"


def _classify_ipv6(path: Path) -> str:
    text = _decode(path)
    try:
        import ipyparse

        sys.modules.setdefault("ipparse", ipyparse)
        from ipyparse.ipv6 import IPv6_WholeString
    except ImportError as exc:
        return f"EnvError:{type(exc).__name__}"

    try:
        ref_value: int | None = int(ipaddress.IPv6Address(text))
        ref_ok = True
    except ipaddress.AddressValueError:
        ref_value = None
        ref_ok = False
    except ValueError:
        ref_value = None
        ref_ok = False

    try:
        sut_value = IPv6_WholeString.parse_string(text, parse_all=True)[0]
        sut_ok = True
    except Exception as exc:
        sut_value = None
        sut_ok = False
        sut_err_name = type(exc).__name__
        if "ParseException" not in sut_err_name:
            return f"UnexpectedException:{sut_err_name}"

    if ref_ok and not sut_ok:
        return "RejectedValidIPv6"
    if not ref_ok and sut_ok:
        return "AcceptedInvalidIPv6"
    if ref_ok and sut_ok and sut_value != ref_value:
        return "SemanticMismatchIPv6"
    return "NoIssue"


def _classify_cidrize(path: Path) -> str:
    text = _decode(path)
    try:
        import cidrize
        from netaddr import IPNetwork
    except ImportError as exc:
        return f"EnvError:{type(exc).__name__}"

    def _alarm_handler(signum, frame):  # noqa: ANN001
        raise TimeoutError("cidrize timeout")

    prev_handler = signal.signal(signal.SIGALRM, _alarm_handler)
    signal.alarm(10)
    try:
        try:
            first = cidrize.cidrize(text, raise_errors=True)
        except TimeoutError:
            return "PerformanceBug"
        except cidrize.CidrizeError:
            return "NoIssue"
        except ValueError:
            return "NoIssue"
        except Exception as exc:
            return f"UnexpectedException:{type(exc).__name__}"

        try:
            round_trip_inputs = [str(net) for net in first]
            second_nets: list[IPNetwork] = []
            for rt in round_trip_inputs:
                second_nets.extend(cidrize.cidrize(rt, raise_errors=True))
        except TimeoutError:
            return "PerformanceBug"
        except Exception:
            return "RoundTripMismatch"

        if sorted(str(n) for n in first) != sorted(str(n) for n in second_nets):
            return "RoundTripMismatch"
        return "NoIssue"
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, prev_handler)


_CLASSIFIERS = {
    "json": _classify_json,
    "ipv4": _classify_ipv4,
    "ipv6": _classify_ipv6,
    "cidrize_ipv4": _classify_cidrize,
    "cidrize_ipv6": _classify_cidrize,
}


def iter_crash_files(crashes_dir: Path) -> list[Path]:
    return sorted(
        p for p in crashes_dir.iterdir() if p.is_file() and p.name.startswith("id:")
    )


def _find_crashes_dir(run_dir: Path) -> Path:
    # Accept either the run dir (AFL output root) or the crashes dir itself.
    if run_dir.name == "crashes":
        return run_dir
    candidate = run_dir / "default" / "crashes"
    if candidate.is_dir():
        return candidate
    # Fallback: first crashes dir found under run_dir
    for child in run_dir.rglob("crashes"):
        if child.is_dir():
            return child
    raise FileNotFoundError(f"no crashes dir under {run_dir}")


def summarize(target: str, run_dir: Path) -> dict:
    if target not in _CLASSIFIERS:
        raise ValueError(
            f"unknown target {target!r}; expected one of {list(_CLASSIFIERS)}"
        )
    classifier = _CLASSIFIERS[target]
    crashes_dir = _find_crashes_dir(run_dir)

    files = iter_crash_files(crashes_dir)
    counts: Counter[str] = Counter()
    dedup: dict[str, list[str]] = defaultdict(list)
    for path in files:
        label = classifier(path)
        counts[label] += 1
        dedup[label].append(path.name)

    return {
        "target": target,
        "crashes_dir": str(crashes_dir),
        "total_artifacts": len(files),
        "counts": dict(sorted(counts.items())),
        "unique_labels": sorted(counts),
        "unique_label_count": len(counts),
        "examples": {label: sorted(names)[:3] for label, names in dedup.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument(
        "--target",
        required=True,
        choices=sorted(_CLASSIFIERS),
        help="Target name to pick the classifier",
    )
    parser.add_argument(
        "run_dir",
        type=Path,
        help="AFL run dir (contains default/crashes/) or a crashes/ dir directly",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Optional path for summary.json (default: <run_dir>/summary.json)",
    )
    args = parser.parse_args()

    summary = summarize(args.target, args.run_dir)

    out_path = args.json_out or (args.run_dir / "summary.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2) + "\n")

    print(f"target: {summary['target']}")
    print(f"crashes_dir: {summary['crashes_dir']}")
    print(f"artifacts: {summary['total_artifacts']}")
    for label, count in summary["counts"].items():
        print(f"  {label}: {count}")
    print(f"summary written to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
