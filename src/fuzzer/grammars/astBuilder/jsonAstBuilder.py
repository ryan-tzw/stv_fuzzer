from ..antlr.json.jsonVisitor import jsonVisitor
from ..antlr.json.jsonParser import jsonParser
from .astNode import AstNode


class jsonAstBuilder(jsonVisitor):
    """
    Build a compact AST for the json grammar:
      Json -> value
      jsonObject -> Object(children=Pair...)
      member -> Pair(Key, Value)
      array -> Array(children=Value...)
      string -> String(value)
      number -> Number(value)
      true/false -> Boolean(value)
      null -> Null(value=None)
    """

    # top-level JSON
    def visitJson(self, ctx: jsonParser.JsonContext):
        return self.visit(ctx.value())

    def visitValue(self, ctx: jsonParser.ValueContext):
        if ctx.jsonObject():
            return self.visit(ctx.jsonObject())
        if ctx.array():
            return self.visit(ctx.array())
        if ctx.string():
            return self.visit(ctx.string())
        if ctx.number():
            return self.visit(ctx.number())
        if ctx.jsonBool():
            return self.visit(ctx.jsonBool())
        if ctx.nullValue():
            return self.visit(ctx.nullValue())

        return AstNode("UnknownValue", value=ctx.getText())

    def visitJsonObject(self, ctx: jsonParser.JsonObjectContext):
        members = [self.visit(m) for m in ctx.member()]
        return AstNode("Object", children=members)

    def visitMember(self, ctx: jsonParser.MemberContext):
        # member : string ':' value
        key_node = self.visit(ctx.string())
        value_node = self.visit(ctx.value())

        return AstNode(
            "Pair", children=[AstNode("Key", value=key_node.value), value_node]
        )

    def visitArray(self, ctx: jsonParser.ArrayContext):
        items = [self.visit(v) for v in ctx.value()]
        return AstNode("Array", children=items)

    def visitString(self, ctx: jsonParser.StringContext):
        t = ctx.STRING()
        if t is None:
            return AstNode("String", value="")

        text = t.getText()

        # remove quotes
        if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
            text = text[1:-1]

        return AstNode("String", value=text)

    def visitNumber(self, ctx: jsonParser.NumberContext):
        return AstNode("Number", value=ctx.getText())

    def visitTrueValue(self, ctx: jsonParser.TrueValueContext):
        return AstNode("Boolean", value=True)

    def visitFalseValue(self, ctx: jsonParser.FalseValueContext):
        return AstNode("Boolean", value=False)

    def visitNullValue(self, ctx: jsonParser.NullValueContext):
        return AstNode("Null", value=None)


if __name__ == "__main__":
    from antlr4 import InputStream, CommonTokenStream
    from ..antlr.json.jsonLexer import jsonLexer

    def parse_json(text: str):
        input_stream = InputStream(text)
        lexer = jsonLexer(input_stream)
        token_stream = CommonTokenStream(lexer)
        parser = jsonParser(token_stream)

        tree = parser.json()
        builder = jsonAstBuilder()
        ast = builder.visit(tree)
        return ast

    test_inputs = [
        '{"name": "Alice", "age": 30}',
        '{"a": 1, "b": true, "c": null}',
        "[1, 2, 3, 4]",
        '{"nested": {"x": 1, "y": [10, 20]}}',
        '{"array": ["a", "b", "c"], "flag": false}',
    ]

    for js in test_inputs:
        print("=" * 50)
        print("Input:", js)
        ast = parse_json(js)
        print("AST:", ast)
