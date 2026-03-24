"""
Generic Unparser - converts any AST back to text.

This unparser works with any AST structure by recursively traversing
and reconstructing text. It uses heuristics for spacing/formatting
based on node types.
"""

from .baseUnparser import Unparser
from ..astBuilder.astNode import AstNode


class GenericUnparser(Unparser):
    """
    Universal unparser that works with any AST structure.

    Strategy:
    - Leaf nodes (value only) → return value as string
    - Internal nodes → recursively unparse children and join
    - Uses node type hints for smart spacing (e.g., "Pair" → add colons)
    """

    def __init__(self, spacing_rules: dict[str, str] | None = None):
        """
        Args:
            spacing_rules: Map of node types to join patterns.
                          Example: {"Pair": "{0}: {1}"}
                          {0}, {1}, etc. are placeholders for children.
        """
        self.spacing_rules = spacing_rules or {}

    def unparse(self, node: AstNode) -> str:
        """
        Recursively unparse an AST node to text.

        Returns:
            String representation of the node.
        """
        if node is None:
            return ""

        # Leaf node - return value
        if not node.children:
            if node.value is not None:
                return str(node.value)
            return ""

        # Internal node - recursively unparse children
        child_texts = [self.unparse(child) for child in node.children]

        # Check for custom spacing rule
        if node.type in self.spacing_rules:
            pattern = self.spacing_rules[node.type]
            try:
                return pattern.format(*child_texts)
            except IndexError, KeyError:
                pass

        # Default: join children with smart spacing
        return self._default_join(node.type, child_texts)

    def _default_join(self, node_type: str, child_texts: list[str]) -> str:
        """
        Apply default joining strategy for node type.

        Uses heuristics based on common AST patterns:
        - Container types (Object, Array, Block) → with brackets and commas
        - Operator-like types → with spaces
        - Others → just concatenate
        """
        if not child_texts:
            return ""

        if len(child_texts) == 1:
            return child_texts[0]

        # Container-like structures
        if node_type in ("Object", "JsonObject", "Block", "Program"):
            return "{" + ", ".join(child_texts) + "}"

        if node_type in ("Array", "JsonArray", "List"):
            return "[" + ", ".join(child_texts) + "]"

        # Pair-like (key-value)
        if node_type in ("Pair", "Member", "Property", "Entry"):
            if len(child_texts) >= 2:
                return f'"{child_texts[0]}": {child_texts[1]}'
            return ": ".join(child_texts)

        # Binary operations
        if node_type in ("BinOp", "Comparison", "Assignment"):
            if len(child_texts) == 2:
                return f"{child_texts[0]} {child_texts[1]}"
            return " ".join(child_texts)

        # IP-like dot-separated (IPv4)
        if node_type in ("Ipv4", "DottedDecimal"):
            return ".".join(child_texts)

        # IPv6-like colon-separated
        if node_type in ("Ipv6Full", "Ipv6Compressed"):
            return self._join_ipv6_parts(child_texts)

        # Default: concatenate
        return "".join(child_texts)

    def _join_ipv6_parts(self, parts: list[str]) -> str:
        """
        Join IPv6 parts, handling :: separator correctly.
        """
        result = ""
        for i, part in enumerate(parts):
            if part == "::":
                result += "::"
            elif result and not result.endswith(":"):
                result += ":" + part
            else:
                result += part
        return result
