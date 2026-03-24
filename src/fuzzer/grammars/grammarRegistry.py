"""
Grammar Registry - Central registry for all grammars.

This module manages grammar registration and discovery. It maps grammar names
to their components (parser, ast_builder, operations, unparser) and provides
a factory for creating parser instances.

The registry supports:
1. Explicit registration (for JSON/IP with custom components)
2. Automatic discovery (for new grammars using generic components)
3. Fallback to generic implementations when specific ones aren't available
"""

from __future__ import annotations

from typing import Any, Type
from pathlib import Path
import importlib


class GrammarRegistry:
    """Registry for grammar implementations."""

    def __init__(self):
        self._grammars: dict[str, dict[str, Any]] = {}

    def register(
        self,
        name: str,
        parser_class: Type,
        lexer_class: Type,
        ast_builder_class: Type | None = None,
        operations_class: Type | None = None,
        unparser_class: Type | None = None,
        start_rule: str | None = None,
    ):
        """
        Register a grammar with its components.

        Args:
            name: Grammar name (e.g., 'json', 'ip', 'xml')
            parser_class: ANTLR ParserClass
            lexer_class: ANTLR LexerClass
            ast_builder_class: Custom AstBuilder class (optional, uses generic if None)
            operations_class: Custom Operations class (optional, uses generic if None)
            unparser_class: Custom Unparser class (optional, uses generic if None)
            start_rule: Entry point rule name (auto-discovered if None)
        """
        self._grammars[name.lower()] = {
            "name": name.lower(),
            "parser_class": parser_class,
            "lexer_class": lexer_class,
            "ast_builder_class": ast_builder_class,
            "operations_class": operations_class,
            "unparser_class": unparser_class,
            "start_rule": start_rule,
        }

    def get(self, name: str) -> dict[str, Any] | None:
        """Retrieve grammar configuration by name."""
        return self._grammars.get(name.lower())

    def list_grammars(self) -> list[str]:
        """Return list of registered grammar names."""
        return list(self._grammars.keys())

    def is_registered(self, name: str) -> bool:
        """Check if a grammar is registered."""
        return name.lower() in self._grammars

    def auto_discover_from_antlr_dir(self, antlr_dir: Path):
        """
        Auto-discover grammars by looking for ANTLR-generated files.

        Looks for patterns like:
        - {grammar}Lexer.py and {grammar}Parser.py
        """
        antlr_dir = Path(antlr_dir).resolve()

        grammars_found = set()

        # Find all Lexer.py files
        for lexer_file in antlr_dir.rglob("*Lexer.py"):
            # Extract grammar name
            grammar_name = lexer_file.name.replace("Lexer.py", "").lower()

            # Check if corresponding Parser exists
            parser_file = lexer_file.parent / f"{grammar_name.capitalize()}Parser.py"
            if not parser_file.exists():
                continue

            grammars_found.add(grammar_name)

        return grammars_found

    def register_from_antlr_module_path(
        self, grammar_name: str, module_base: str, use_generic: bool = True
    ):
        """
        Register a grammar by importing from ANTLR module path.

        Args:
            grammar_name: Name of grammar (e.g., 'json', 'ip')
            module_base: Base module path (e.g., 'fuzzer.grammars.antlr.json')
            use_generic: If True, use generic implementations (AstBuilder, Operations, Unparser)
                        if specific ones not found
        """
        grammar_name = grammar_name.lower()

        try:
            # Import lexer and parser
            lexer_mod = importlib.import_module(f"{module_base}.{grammar_name}Lexer")
            parser_mod = importlib.import_module(f"{module_base}.{grammar_name}Parser")

            lexer_class = getattr(lexer_mod, f"{grammar_name.capitalize()}Lexer")
            parser_class = getattr(parser_mod, f"{grammar_name.capitalize()}Parser")

            # Try to load specific implementations
            ast_builder_class = None
            operations_class = None
            unparser_class = None

            if not use_generic:
                # Try to load from grammars.astBuilder.{grammar}AstBuilder
                try:
                    builder_mod = importlib.import_module(
                        f"fuzzer.grammars.astBuilder.{grammar_name}AstBuilder"
                    )
                    ast_builder_class = getattr(
                        builder_mod, f"{grammar_name}AstBuilder"
                    )
                except ImportError, AttributeError:
                    pass

                # Try to load operations
                try:
                    ops_mod = importlib.import_module(
                        f"fuzzer.grammars.operations.{grammar_name}Operations"
                    )
                    operations_class = getattr(
                        ops_mod, f"{grammar_name}GrammarOperations"
                    )
                except ImportError, AttributeError:
                    pass

                # Try to load unparser
                try:
                    unparser_mod = importlib.import_module(
                        f"fuzzer.grammars.unparser.{grammar_name}Unparser"
                    )
                    unparser_class = getattr(unparser_mod, f"{grammar_name}Unparser")
                except ImportError, AttributeError:
                    pass

            self.register(
                grammar_name,
                parser_class=parser_class,
                lexer_class=lexer_class,
                ast_builder_class=ast_builder_class,
                operations_class=operations_class,
                unparser_class=unparser_class,
            )

        except (ImportError, AttributeError) as e:
            raise ValueError(
                f"Failed to register grammar '{grammar_name}' from '{module_base}': {e}"
            )


# Global registry instance
_global_registry = GrammarRegistry()


def get_registry() -> GrammarRegistry:
    """Get the global grammar registry."""
    return _global_registry


def register_grammar(
    name: str,
    parser_class: Type,
    lexer_class: Type,
    ast_builder_class: Type | None = None,
    operations_class: Type | None = None,
    unparser_class: Type | None = None,
    start_rule: str | None = None,
):
    """Convenience function to register a grammar."""
    _global_registry.register(
        name,
        parser_class=parser_class,
        lexer_class=lexer_class,
        ast_builder_class=ast_builder_class,
        operations_class=operations_class,
        unparser_class=unparser_class,
        start_rule=start_rule,
    )


def get_grammar(name: str) -> dict[str, Any] | None:
    """Convenience function to get grammar config."""
    return _global_registry.get(name)


def list_registered_grammars() -> list[str]:
    """Convenience function to list all registered grammars."""
    return _global_registry.list_grammars()
