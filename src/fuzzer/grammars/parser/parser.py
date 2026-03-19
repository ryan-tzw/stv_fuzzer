"""
ANTLR Grammar parser wrapper.

Responsibilities:
- Run ANTLR parser
- Convert CST -> AST using AST builders
- Delegate AST -> string to unparsers
"""

import importlib
from pathlib import Path

import antlr4
from antlr4.error.ErrorStrategy import BailErrorStrategy

from ..astBuilder import jsonAstBuilder, ipAstBuilder
from ..unparser import jsonUnparser, ipUnparser


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
    parser_type = parser_type.lower()

    if parser_type == "json":
        return jsonParser(antlr_dir)
    elif parser_type == "ip":
        return ipParser(antlr_dir)

    raise ValueError(f"Unsupported parser type '{parser_type}'. Use 'json' or 'ip'.")


if __name__ == "__main__":
    from pathlib import Path

    ANTLR_DIR = (Path(__file__).parent.parent / "antlr").resolve()

    print("=" * 60)

    # json test
    print("\nJSON PARSER TESTS")
    print("-" * 60)
    json_parser = jsonParser(ANTLR_DIR)
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
    ip_parser = ipParser(ANTLR_DIR)
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
