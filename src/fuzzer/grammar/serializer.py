"""Serialize internal Node trees back into string form."""

from fuzzer.grammar.tree import Node


def serialize_tree(node: Node) -> str:
    """Serialize a Node subtree into text by recursive concatenation."""
    if node.is_leaf():
        return node.text or ""
    return "".join(serialize_tree(child) for child in node.children)
