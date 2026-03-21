import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any


def _stable_print(obj: Any) -> None:
    sys.stdout.write(json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n")


def _ensure_ipparse_alias() -> None:
    import ipyparse  # type: ignore

    sys.modules.setdefault("ipparse", ipyparse)


def _ensure_project_src_on_syspath() -> None:
    src_dir = Path.cwd() / "src"
    if src_dir.is_dir():
        src_str = str(src_dir)
        if src_str not in sys.path:
            sys.path.insert(0, src_str)


def _parse_family_arg() -> str:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--family",
        choices=["auto", "ipv4", "ipv6"],
        default="auto",
    )
    args, _ = parser.parse_known_args()
    return args.family


def main() -> int:
    _ensure_project_src_on_syspath()
    family = _parse_family_arg()

    raw = sys.stdin.buffer.read()
    s = raw.decode("utf-8", errors="replace")

    try:
        from ipyparse.ipv4 import IPv4  # type: ignore
        from pyparsing import ParseException  # type: ignore

        def parse_ipv4() -> int:
            return IPv4.parse_string(s, parse_all=True)[0]

        def parse_ipv6() -> int:
            _ensure_ipparse_alias()
            from ipyparse.ipv6 import IPv6_WholeString  # type: ignore

            return IPv6_WholeString.parse_string(s)[0]

        if family == "ipv4":
            parsed = parse_ipv4()
        elif family == "ipv6":
            parsed = parse_ipv6()
        else:
            try:
                parsed = parse_ipv4()
            except ParseException:
                parsed = parse_ipv6()

        _stable_print(parsed)
        return 0

    except Exception:
        sys.stderr.write(traceback.format_exc())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
