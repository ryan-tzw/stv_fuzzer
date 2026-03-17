from typing import List, Any, Optional


class AstNode:
    """
    Simple AST node suitable for mutation:
      - type: node type name (string)
      - children: list[AstNode]
      - value: optional scalar for leaf nodes (string, int, bool, None)
    """

    __slots__ = ("type", "children", "value")

    def __init__(
        self, type_: str, children: Optional[List["AstNode"]] = None, value: Any = None
    ):
        self.type = type_
        self.children = list(children) if children else []
        self.value = value

    def __repr__(self):
        if self.value is not None:
            return f"AstNode({self.type!r}, value={self.value!r})"
        return f"AstNode({self.type!r}, children={self.children!r})"
