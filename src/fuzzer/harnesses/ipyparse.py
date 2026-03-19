import json
import sys
import traceback


def _stable_print(value: object) -> None:
    sys.stdout.write(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def _parse_ip(ip_str: str) -> list[int]:
    from ipparse.ipv4 import IPv4  # type: ignore
    from ipparse.ipv6 import IPv6_WholeString  # type: ignore

    if ":" in ip_str:
        return list(IPv6_WholeString.parseString(ip_str))
    return list(IPv4.parseString(ip_str))


def main() -> int:
    raw = sys.stdin.buffer.read()
    if not raw:
        sys.stderr.write("Error: No input provided. IP input is required via stdin.\n")
        return 1

    ip_str = raw.decode("utf-8", errors="replace")

    try:
        parsed = _parse_ip(ip_str)
        _stable_print(parsed)
        return 0
    except Exception:
        sys.stderr.write(f"ERR:{traceback.format_exc()}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
