"""Bridge from Lark parse outputs to internal Node/ParseResult types."""

from lark import Token, Tree
from lark.exceptions import LarkError

from fuzzer.grammar.tree import Node, ParseResult


def parse_input(parser, text: str) -> ParseResult:
    """Parse input text with a loaded Lark parser."""
    try:
        parsed = parser.parse(text)
    except LarkError as exc:
        return ParseResult(success=False, tree=None, errors=[str(exc)])
    except Exception as exc:  # defensive fallback
        return ParseResult(success=False, tree=None, errors=[str(exc)])

    try:
        node = _lark_to_node(parsed)
    except Exception as exc:  # defensive fallback
        return ParseResult(
            success=False,
            tree=None,
            errors=[f"Failed to convert Lark tree: {exc}"],
        )

    return ParseResult(success=True, tree=node, errors=[])


def _lark_to_node(obj: Tree | Token | None) -> Node:
    if isinstance(obj, Tree):
        # Lark may emit None placeholders for omitted optional branches.
        children = [
            converted
            for child in obj.children
            if child is not None
            for converted in [_lark_to_node(child)]
        ]
        return Node(symbol=str(obj.data), children=children, text=None)

    if isinstance(obj, Token):
        return Node(symbol=obj.type, children=[], text=str(obj))

    raise TypeError(f"Unsupported Lark node type: {type(obj)!r}")
