"""
Generic AST Builder - works with any ANTLR-generated parser.

This builder automatically converts ANTLR parse trees (CSTs) into simplified ASTs.
It uses reflection and the visitor pattern to traverse any grammar's parse tree
and produce AstNode objects without requiring grammar-specific code.

Key principles:
- Rule contexts (nodes with children) → AstNode with type=rule_name
- Terminal nodes (TerminalNode) → AstNode with value=token_text
- Filters out noise tokens (whitespace, punctuation typically)
- Uses ANTLR metadata to extract proper token/rule names
"""

from __future__ import annotations

from typing import Any
from antlr4.tree.Tree import TerminalNode, ParseTreeVisitor

from .astNode import AstNode


class GenericAstBuilder(ParseTreeVisitor):
    """
    Universal AST builder that works with any ANTLR grammar.

    Converts parse tree → simplified AST by:
    1. Visiting all child nodes
    2. Extracting rule contexts as internal nodes
    3. Extracting terminals as leaf nodes
    4. Filtering out punctuation/trivial tokens
    5. Using ANTLR metadata for proper token names
    """

    def __init__(self, filter_tokens: set[str] | None = None, parser_class: Any = None):
        """
        Args:
            filter_tokens: Set of token names to skip (e.g. {'WS', 'LPAREN'}).
                          If None, uses default filtering.
            parser_class: Optional ANTLR parser class to extract metadata
                         (symbolic names, literal names) for better token naming.
        """
        super().__init__()
        # Default tokens to filter out (common noise)
        self.filter_tokens = filter_tokens or {
            "WS",
            "LPAREN",
            "RPAREN",
            "LBRACE",
            "RBRACE",
            "LBRACKET",
            "RBRACKET",
            "SEMICOLON",
            "COLON",
            "COMMA",
            "DOT",
            "EQUALS",
        }

        # Try to extract metadata from parser class
        self.symbolic_names = {}
        self.literal_names = {}
        if parser_class:
            try:
                parser_instance = parser_class(None)
                if hasattr(parser_instance, "symbolicNames"):
                    self.symbolic_names = {
                        i: name
                        for i, name in enumerate(parser_instance.symbolicNames)
                        if name and name != "<INVALID>"
                    }
                if hasattr(parser_instance, "literalNames"):
                    self.literal_names = {
                        i: name
                        for i, name in enumerate(parser_instance.literalNames)
                        if name and name != "<INVALID>"
                    }
            except Exception:
                pass  # Parser metadata not available, fall back to defaults

    def visit(self, tree: Any) -> AstNode | None:
        """
        Visit any parse tree node and convert to AstNode.

        Returns None if tree is None, otherwise returns AstNode.
        """
        if tree is None:
            return None

        if isinstance(tree, TerminalNode):
            return self._visit_terminal(tree)
        else:
            return self._visit_rule_context(tree)

    def _visit_terminal(self, node: TerminalNode) -> AstNode | None:
        """Convert terminal node to AstNode."""
        symbol = node.getSymbol()
        if symbol is None:
            return None

        # Get token name from symbol
        token_name = self._get_token_name(node)

        # Skip filtered tokens
        if token_name in self.filter_tokens:
            return None

        # Create leaf node with token value
        text = node.getText()
        return AstNode(token_name, value=text)

    def _visit_rule_context(self, node: Any) -> AstNode | None:
        """Convert rule context to AstNode."""
        if node is None:
            return None

        # Get rule name
        rule_name = self._get_rule_name(node)

        # Visit all children and filter Nones
        children = []
        for i in range(node.getChildCount()):
            child = node.getChild(i)
            child_node = self.visit(child)
            if child_node is not None:
                children.append(child_node)

        # If no children survived filtering, treat as leaf with text
        if not children:
            text = node.getText()
            if text:
                return AstNode(rule_name, value=text)
            return AstNode(rule_name)

        return AstNode(rule_name, children=children)

    def _get_rule_name(self, node: Any) -> str:
        """Extract rule name from parse tree context."""
        class_name = node.__class__.__name__

        # Remove "Context" suffix if present
        if class_name.endswith("Context"):
            return class_name[:-7]

        return class_name

    def _get_token_name(self, terminal: TerminalNode) -> str:
        """
        Extract symbolic token name from terminal node.

        Uses ANTLR metadata if available, falls back to heuristics.
        """
        symbol = terminal.getSymbol()
        if symbol is None:
            return "Token"

        # Try to use ANTLR metadata first
        if hasattr(symbol, "type") and symbol.type in self.symbolic_names:
            name = self.symbolic_names[symbol.type]
            if name and name != "<INVALID>":
                return name

        # Try literal names as fallback
        if hasattr(symbol, "type") and symbol.type in self.literal_names:
            name = self.literal_names[symbol.type]
            if name and name != "<INVALID>":
                # Remove quotes from literal names
                return name.strip("'\"")

        # Ultimate fallback: use text as token identifier
        text = terminal.getText()
        if text and text.strip():
            # For operators and punctuation, return the text itself
            if len(text) <= 3 and not text.isalnum():
                return text
            return f"Token_{text}"

        return "Token"
