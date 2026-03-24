from __future__ import annotations

import ipaddress
import json
import random
import string
from collections.abc import Callable


def _random_string_token() -> str:
    alphabet = string.ascii_letters + string.digits + " _-:/"
    length = random.randint(0, 12)
    value = "".join(random.choice(alphabet) for _ in range(length))
    return json.dumps(value, ensure_ascii=True)


def _random_number_token() -> str:
    choice = random.randrange(5)
    if choice == 0:
        return str(random.randint(-10, 10))
    if choice == 1:
        return str(random.randint(-10000, 10000))
    if choice == 2:
        return json.dumps(round(random.uniform(-1000, 1000), 3))
    if choice == 3:
        return f"{random.randint(-999, 999)}e{random.randint(-5, 5)}"
    return random.choice(["0", "1", "-1", "2147483647", "-2147483648"])


def _ipv4_octet() -> str:
    value = random.randint(0, 255)
    width = random.choice([1, 1, 1, 2, 3])
    return str(value).zfill(width)


def _ipv6_hextet() -> str:
    return f"{random.randint(0, 0xFFFF):x}"


def _ipv6_address() -> str:
    value = ipaddress.IPv6Address(random.getrandbits(128))
    return value.compressed


def _cidr_prefix() -> str:
    return str(random.randint(0, 32))


def _short_range_end() -> str:
    return str(random.randint(0, 255))


def _bracket_range() -> str:
    start = random.randint(0, 8)
    end = random.randint(start + 1, 9)
    return f"[{start}-{end}]"


def _bracket_set() -> str:
    digits = sorted({str(random.randint(0, 9)) for _ in range(random.randint(2, 5))})
    return "[" + "".join(digits) + "]"


TERMINAL_GENERATORS: dict[str, Callable[[], str]] = {
    "json_string": _random_string_token,
    "json_number": _random_number_token,
    "ipv4_octet": _ipv4_octet,
    "ipv6_hextet": _ipv6_hextet,
    "ipv6_address": _ipv6_address,
    "cidr_prefix": _cidr_prefix,
    "short_range_end": _short_range_end,
    "bracket_range": _bracket_range,
    "bracket_set": _bracket_set,
}


def resolve_terminal_generator(name: str) -> Callable[[], str]:
    try:
        return TERMINAL_GENERATORS[name]
    except KeyError as exc:  # pragma: no cover - defensive only
        raise KeyError(f"Unknown terminal generator: {name}") from exc
