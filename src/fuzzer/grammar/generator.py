"""Grammar-based string generator built from loaded Lark grammars."""

import random
from dataclasses import dataclass
from pathlib import Path

from fuzzer.grammar.loader import load_parser


@dataclass(frozen=True)
class _GenerationSpec:
    productions: dict[str, list[tuple[str, ...]]]
    terminal_literals: dict[str, str]
    terminals: set[str]
    ignored_terminals: set[str]


class _DepthLimitError(ValueError):
    """Raised when no expansion can satisfy the configured depth limit."""


def generate_from_grammar(
    name_or_path: str | Path,
    *,
    start_symbol: str = "start",
    rng: random.Random | None = None,
    max_depth: int = 8,
) -> str:
    """Generate one candidate string by recursively expanding grammar symbols."""
    if max_depth < 1:
        raise ValueError(f"max_depth must be >= 1, got {max_depth}")

    parser = load_parser(name_or_path)
    spec = _build_generation_spec(parser)
    engine_rng = rng or random.Random()

    attempts = 20
    for _ in range(attempts):
        try:
            return _expand_symbol(
                start_symbol,
                spec,
                engine_rng,
                depth=0,
                max_depth=max_depth,
            )
        except _DepthLimitError:
            continue

    raise ValueError(
        f"Unable to generate from {name_or_path!r} within max_depth={max_depth}"
    )


def _build_generation_spec(parser) -> _GenerationSpec:
    productions: dict[str, list[tuple[str, ...]]] = {}
    for rule in parser.rules:
        origin = rule.origin.name
        expansion = tuple(symbol.name for symbol in rule.expansion)
        productions.setdefault(origin, []).append(expansion)

    terminal_literals: dict[str, str] = {}
    terminals: set[str] = set()
    for terminal in parser.terminals:
        terminals.add(terminal.name)
        pattern = terminal.pattern
        if pattern.__class__.__name__ == "PatternStr":
            terminal_literals[terminal.name] = pattern.value

    return _GenerationSpec(
        productions=productions,
        terminal_literals=terminal_literals,
        terminals=terminals,
        ignored_terminals=set(parser.ignore_tokens),
    )


def _expand_symbol(
    symbol: str,
    spec: _GenerationSpec,
    rng: random.Random,
    *,
    depth: int,
    max_depth: int,
) -> str:
    if symbol in spec.productions:
        production = _choose_production(
            symbol, spec, rng, depth=depth, max_depth=max_depth
        )
        return "".join(
            _expand_symbol(
                part,
                spec,
                rng,
                depth=depth + 1,
                max_depth=max_depth,
            )
            for part in production
        )

    return _generate_terminal(symbol, spec, rng)


def _choose_production(
    symbol: str,
    spec: _GenerationSpec,
    rng: random.Random,
    *,
    depth: int,
    max_depth: int,
) -> tuple[str, ...]:
    productions = spec.productions.get(symbol, [])
    if not productions:
        raise ValueError(f"No productions found for nonterminal {symbol!r}")

    if depth >= max_depth:
        safe = [prod for prod in productions if _nonterminal_count(prod, spec) == 0]
        if not safe:
            raise _DepthLimitError(
                f"Max depth reached while expanding {symbol!r}; "
                "no terminal-only production available."
            )
        return rng.choice(safe)

    if depth == max_depth - 1:
        min_count = min(_nonterminal_count(prod, spec) for prod in productions)
        preferred = [
            prod for prod in productions if _nonterminal_count(prod, spec) == min_count
        ]
        return rng.choice(preferred)

    return rng.choice(productions)


def _nonterminal_count(production: tuple[str, ...], spec: _GenerationSpec) -> int:
    return sum(1 for symbol in production if symbol in spec.productions)


def _generate_terminal(symbol: str, spec: _GenerationSpec, rng: random.Random) -> str:
    if symbol in spec.ignored_terminals:
        return ""
    if symbol in spec.terminal_literals:
        return spec.terminal_literals[symbol]

    generator = _TERMINAL_GENERATORS.get(symbol)
    if generator is not None:
        return generator(rng)

    if symbol in spec.terminals:
        raise ValueError(f"No generator registered for non-literal terminal {symbol!r}")

    raise ValueError(f"Unknown grammar symbol {symbol!r}")


def _gen_digit(rng: random.Random) -> str:
    return str(rng.randint(0, 9))


def _gen_octet(rng: random.Random) -> str:
    return str(rng.randint(0, 255))


def _gen_hextet(rng: random.Random) -> str:
    width = rng.randint(1, 4)
    alphabet = "0123456789abcdef"
    return "".join(rng.choice(alphabet) for _ in range(width))


def _gen_signed_number(rng: random.Random) -> str:
    sign = rng.choice(["", "", "-", "+"])
    whole = str(rng.randint(0, 9999))
    if rng.random() < 0.35:
        fraction = str(rng.randint(0, 9999)).rstrip("0")
        if not fraction:
            fraction = "0"
        return f"{sign}{whole}.{fraction}"
    return f"{sign}{whole}"


def _gen_escaped_string(rng: random.Random) -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-"
    length = rng.randint(0, 12)
    value = "".join(rng.choice(alphabet) for _ in range(length))
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


_TERMINAL_GENERATORS = {
    "DIGIT": _gen_digit,
    "OCTET": _gen_octet,
    "HEXTET": _gen_hextet,
    "SIGNED_NUMBER": _gen_signed_number,
    "ESCAPED_STRING": _gen_escaped_string,
}
