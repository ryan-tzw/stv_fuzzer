"""
ANTLR Grammar parser wrapper.

Responsibilities:
- Run ANTLR parser
- Convert CST -> AST using AST builders
- Delegate AST -> string to unparsers

Supports both:
- Backward-compatible factory (jsonParser, ipParser) for existing code
- New registry-based factory for generic grammar support
"""

import importlib
from pathlib import Path

import antlr4
from antlr4.error.ErrorStrategy import BailErrorStrategy

from ..astBuilder import jsonAstBuilder, ipAstBuilder, GenericAstBuilder
from ..unparser import jsonUnparser, ipUnparser, GenericUnparser
from ..grammarRegistry import get_registry


class GrammarParser:
    """Base class for all grammar parsers."""

    def __init__(self, target: str, antlr_dir: str | Path, builder_cls, unparser_cls):

        self.target = target.lower()
        self.antlr_dir = Path(antlr_dir).resolve()
        self.prefix = self._discover_prefix()

        module_base = f"fuzzer.grammars.antlr.{self.target}"
        lexer_mod = importlib.import_module(f"{module_base}.{self.prefix}Lexer")
        parser_mod = importlib.import_module(f"{module_base}.{self.prefix}Parser")
        self.LexerClass = getattr(lexer_mod, f"{self.prefix}Lexer")
        self.ParserClass = getattr(parser_mod, f"{self.prefix}Parser")

        self.start_rule = self._get_start_rule()
        self.builder = builder_cls()
        self.unparser = unparser_cls()

    def _discover_prefix(self):
        for file in self.antlr_dir.rglob("*Lexer.py"):
            prefix = file.name.replace("Lexer.py", "")
            if prefix.lower() == self.target:
                return prefix
        raise ValueError(f"No ANTLR lexer found for grammar '{self.target}'")

    def _get_start_rule(self):
        parser = self.ParserClass(None)
        return parser.ruleNames[0]

    def parse(self, data: str):
        input_stream = antlr4.InputStream(data)
        lexer = self.LexerClass(input_stream)
        lexer.removeErrorListeners()
        token_stream = antlr4.CommonTokenStream(lexer)

        parser = self.ParserClass(token_stream)
        parser.removeErrorListeners()
        parser._errHandler = BailErrorStrategy()

        try:
            parse_method = getattr(parser, self.start_rule)
            cst = parse_method()

        except Exception as e:
            raise ValueError(f"Input failed to parse: {data}") from e

        ast = self.builder.visit(cst)
        return ast

    def unparse(self, ast):
        return self.unparser.unparse(ast)


class jsonParser(GrammarParser):
    def __init__(self, antlr_dir):
        super().__init__(
            "json",
            antlr_dir,
            builder_cls=jsonAstBuilder,
            unparser_cls=jsonUnparser,
        )


class ipParser(GrammarParser):
    def __init__(self, antlr_dir):
        super().__init__(
            target="ip",
            antlr_dir=antlr_dir,
            builder_cls=ipAstBuilder,
            unparser_cls=ipUnparser,
        )


def create_parser(parser_type: str, antlr_dir):
    """
    Factory function to create a parser for any grammar.

    Strategy:
    1. First, check if grammar is in registry (for pre-registered grammars)
    2. If not found, try to auto-discover and use generic implementations
    3. Fall back to hardcoded JSON/IP for backward compatibility

    Args:
        parser_type: Grammar name (e.g., 'json', 'ip', 'xml', 'csv')
        antlr_dir: Path to ANTLR-generated files directory

    Returns:
        GrammarParser instance (either specific or generic)

    Raises:
        ValueError: If grammar cannot be found or loaded
    """
    parser_type = parser_type.lower()

    # hardcoded JSON/IP
    if parser_type == "json":
        return jsonParser(antlr_dir)
    elif parser_type == "ip":
        return ipParser(antlr_dir)

    # Try registry-based approach (for new grammars)
    registry = get_registry()
    grammar_config = registry.get(parser_type)

    if grammar_config:
        # Grammar is registered - use it
        builder_cls = grammar_config.get("ast_builder_class") or GenericAstBuilder
        unparser_cls = grammar_config.get("unparser_class") or GenericUnparser
        return GrammarParser(parser_type, antlr_dir, builder_cls, unparser_cls)

    # Try auto-discovery with generic implementations
    try:
        return GrammarParser(
            parser_type,
            antlr_dir,
            builder_cls=GenericAstBuilder,
            unparser_cls=GenericUnparser,
        )
    except Exception as e:
        raise ValueError(
            f"Unsupported parser type '{parser_type}'. "
            f"Use 'json', 'ip', or register a custom grammar. Error: {e}"
        )


if __name__ == "__main__":
    from pathlib import Path

    ANTLR_DIR = (Path(__file__).parent.parent / "antlr").resolve()

    print("=" * 60)

    # json test
    print("\nJSON PARSER TESTS")
    print("-" * 60)
    json_parser = create_parser("json", ANTLR_DIR)
    json_tests = [
        '{"name": "Alice", "age": 30}',
        '{"a": 1, "b": true, "c": null}',
        "[1,2,3,4]",
        '{"nested": {"x": 1, "y": [10,20]}}',
        '{"array": ["a","b","c"], "flag": false}',
    ]
    for test in json_tests:
        print("\nInput:", test)
        try:
            ast = json_parser.parse(test)
            print("AST:", ast)
            reconstructed = json_parser.unparse(ast)
            print("Reconstructed:", reconstructed)
        except Exception as e:
            print("Parse failed:", e)

    print("\n" + "=" * 60)

    # ip_test
    print("\nIP PARSER TESTS")
    print("-" * 60)
    ip_parser = create_parser("ip", ANTLR_DIR)
    ip_tests = [
        # IPv4 allowed inputs
        "0.0.0.0",
        "00.01.002.000",
        "1.2.3.4",
        "09.10.99.100",
        "127.0.0.1",
        "192.168.001.001",
        "249.250.251.252",
        "255.255.255.255",
        # IPv6 allowed inputs
        "2001:0db8:0000:0000:0000:ff00:0042:8329",
        "2001:db8:0:0:0:0:192.0.2.33",
        "2001:db8::",
        "2001:db8::1",
        "2001:db8::192.0.2.33",
        "2001:db8::1:2",
        "2001:db8::1:192.0.2.33",
        "2001:db8::1:2:3",
        "2001:db8::1:2:192.0.2.33",
        "2001:db8::1:2:3:4",
        "2001:db8::1:2:3:192.0.2.33",
        "2001:db8::1:2:3:4:5",
        "2001::1:2:3:4:5:6",
        "::192.0.2.33",
        # cidrize
        "192.168.1.0/24",
        "0.0.0.0/0",
        "192.0.2.80-192.0.2.85",
        "192.0.2.170-175",
        "192.0.2.8[0-5]",
        "21.43.180.1[40-99]",
        "192.0.2.[5678]",
        "15.63.148.*",
        "2001:0db8:0000:0000:0000:ff00:0042:8329/128",
        "2001:db8::-2001:db8::ff",
    ]
    for test in ip_tests:
        print("\nInput:", test)
        try:
            ast = ip_parser.parse(test)
            print("AST:", ast)
            reconstructed = ip_parser.unparse(ast)
            print("Reconstructed:", reconstructed)
        except Exception as e:
            print("Parse failed:", e)

    print("\n" + "=" * 60)

    print("\nARITHMETIC PARSER TESTS (using GenericAstBuilder + GenericUnparser)")
    print("-" * 60)
    arith_parser = create_parser("arithmetic", ANTLR_DIR)

    arith_tests = [
        "1+2*3",
        "(4-5)/6",
        "10",
        "2*(3+4)",
        "100-20+3*4/2",
        "(1+2)*(3-4)",
        "42/7+8*9",
        "123+456*789-0",
        "(10+20)*(30/5)-7",
    ]

    for test in arith_tests:
        print("\nInput:", test)
        try:
            ast = arith_parser.parse(test)
            print("AST:", ast)
            reconstructed = arith_parser.unparse(ast)
            print("Reconstructed:", reconstructed)
            # Quick validation
            print("Round-trip OK" if reconstructed == test else "Round-trip MISMATCH!")
        except Exception as e:
            print("Parse failed:", e)

    print("\n" + "=" * 60)
