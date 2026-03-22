from ..antlr.ip.ipVisitor import ipVisitor
from ..antlr.ip.ipParser import ipParser
from .astNode import AstNode
from antlr4 import TerminalNode


class ipAstBuilder(ipVisitor):
    """
    Build a compact AST for the ip grammar.

    Produced node types:
      - Ipv4 (children = Octet nodes)
      - Octet (value = string, e.g. "192" or "001")
      - Ipv6Full / Ipv6Compressed (children = H16 / DoubleColon / Ipv4 nodes)
      - H16 (value = string)
      - DoubleColon (value = "::")
      - Ipv4Cidr / Ipv6Cidr (children = IP node, Prefix node)
      - Ipv4Range / Ipv4ShorthandRange / Ipv6Range
      - Ipv4Bracket / Ipv4BracketOctets
      - Ipv4Wildcard
      - PrefixV4 / PrefixV6 / BracketContent (value = string)
    """

    # ROOT
    def visitIpExpression(self, ctx: ipParser.IpExpressionContext):
        """Entry point - matches the root rule of the new grammar."""
        if ctx.ipv4Expression():
            return self.visit(ctx.ipv4Expression())
        if ctx.ipv6Expression():
            return self.visit(ctx.ipv6Expression())
        return AstNode("IpExpr", value=ctx.getText())

    # IPv4 EXPRESSIONS
    def visitIpv4Expression(self, ctx: ipParser.Ipv4ExpressionContext):
        ipv4_addrs = ctx.ipv4Address()
        # CIDR: 192.168.1.1/24
        if ctx.SLASH():
            return AstNode(
                "Ipv4Cidr",
                children=[self.visit(ipv4_addrs[0]), self.visit(ctx.prefixV4())],
            )
        # Ranges: 10.0.0.1-10.0.0.5 or 10.0.0.1-5
        if ctx.HYPHEN():
            if len(ipv4_addrs) == 2:
                # Full hyphen range
                return AstNode(
                    "Ipv4Range",
                    children=[self.visit(ipv4_addrs[0]), self.visit(ipv4_addrs[1])],
                )
            else:
                # Shorthand hyphen range
                return AstNode(
                    "Ipv4ShorthandRange",
                    children=[self.visit(ipv4_addrs[0]), self.visit(ctx.ipv4Octet(0))],
                )
        # Bracket forms: 10.0.0.1[0-5] or 10.0.0.[0-5]
        if ctx.LBRACKET():
            bracket_content = self.visit(ctx.bracketContent())
            if ipv4_addrs:
                # Form 1: ipv4Address LBRACKET bracketContent RBRACKET
                return AstNode(
                    "Ipv4Bracket", children=[self.visit(ipv4_addrs[0]), bracket_content]
                )
            else:
                # Form 2: ipv4Octet DOT ipv4Octet DOT ipv4Octet DOT LBRACKET bracketContent RBRACKET
                octets = [self.visit(o) for o in ctx.ipv4Octet()]
                return AstNode("Ipv4BracketOctets", children=[*octets, bracket_content])
        # Wildcard: 10.0.0.*
        if ctx.ASTERISK():
            octets = [self.visit(o) for o in ctx.ipv4Octet()]
            return AstNode("Ipv4Wildcard", children=octets)
        # Lone IPv4 (Host Route)
        if ipv4_addrs:
            return self.visit(ipv4_addrs[0])
        return AstNode("UnknownIpv4Expr", value=ctx.getText())

    # IPv6 EXPRESSIONS
    def visitIpv6Expression(self, ctx: ipParser.Ipv6ExpressionContext):
        ipv6_addrs = ctx.ipv6Address()
        # CIDR: 2001:db8::/32
        if ctx.SLASH():
            return AstNode(
                "Ipv6Cidr",
                children=[self.visit(ipv6_addrs[0]), self.visit(ctx.prefixV6())],
            )
        # Range: 2001:db8::1-2001:db8::5
        if ctx.HYPHEN():
            return AstNode(
                "Ipv6Range",
                children=[self.visit(ipv6_addrs[0]), self.visit(ipv6_addrs[1])],
            )
        # Lone IPv6 (Host Route)
        if ipv6_addrs:
            return self.visit(ipv6_addrs[0])
        return AstNode("UnknownIpv6Expr", value=ctx.getText())

    # IPv4 BASE
    def visitIpv4Address(self, ctx: ipParser.Ipv4AddressContext):
        octets = [self.visit(o) for o in ctx.ipv4Octet()]
        return AstNode("Ipv4", children=octets)

    def visitIpv4Octet(self, ctx: ipParser.Ipv4OctetContext):
        return AstNode("Octet", value=ctx.getText())

    def visitPrefixV4(self, ctx: ipParser.PrefixV4Context):
        return AstNode("PrefixV4", value=ctx.getText())

    def visitBracketContent(self, ctx: ipParser.BracketContentContext):
        return AstNode("BracketContent", value=ctx.getText())

    # IPv6 BASE
    def visitIpv6Address(self, ctx: ipParser.Ipv6AddressContext):
        """
        Unified handler for ALL IPv6 forms (full + every compressed variant).
        """
        children = []
        i = 0
        while i < len(ctx.children):
            child = ctx.children[i]

            if isinstance(child, TerminalNode):
                if child.getText() == ":":
                    # Detect "::" (two consecutive COLON tokens)
                    if (
                        i + 1 < len(ctx.children)
                        and isinstance(ctx.children[i + 1], TerminalNode)
                        and ctx.children[i + 1].getText() == ":"
                    ):
                        children.append(AstNode("DoubleColon", value="::"))
                        i += 2
                        continue
                i += 1
                continue

            elif isinstance(child, ipParser.H16Context):
                children.append(self.visit(child))

            elif isinstance(child, ipParser.Ipv4AddressContext):
                children.append(self.visit(child))

            elif isinstance(child, ipParser.Ls32Context):
                sub = self.visitLs32(child)
                if isinstance(sub, list):
                    children.extend(sub)
                else:
                    children.append(sub)

            i += 1

        is_compressed = any(
            isinstance(c, AstNode) and c.type == "DoubleColon" for c in children
        )
        node_type = "Ipv6Compressed" if is_compressed else "Ipv6Full"
        return AstNode(node_type, children=children)

    def visitH16(self, ctx: ipParser.H16Context):
        return AstNode("H16", value=ctx.getText())

    def visitLs32(self, ctx: ipParser.Ls32Context):
        """
        ls32 can be either:
          - h16 ":" h16   → return two H16 nodes (flattened into IPv6 groups)
          - ipv4Address   → return the Ipv4 node (for dual-stack ::ffff:...)
        """
        if ctx.ipv4Address():
            return self.visit(ctx.ipv4Address())
        return [self.visit(h) for h in ctx.h16()]

    def visitPrefixV6(self, ctx: ipParser.PrefixV6Context):
        return AstNode("PrefixV6", value=ctx.getText())

    # HELPERS
    def _as_list(self, x):
        return x if isinstance(x, list) else [x] if x else []


if __name__ == "__main__":
    from antlr4 import InputStream, CommonTokenStream
    from ..antlr.ip.ipLexer import ipLexer

    def parse_ip_expr(text: str):
        input_stream = InputStream(text)
        lexer = ipLexer(input_stream)
        token_stream = CommonTokenStream(lexer)
        parser = ipParser(token_stream)

        tree = parser.ipExpression()
        builder = ipAstBuilder()
        ast = builder.visit(tree)
        return ast

    test_inputs = [
        # IPv4 (leading zeros allowed)
        "0.0.0.0",
        "00.01.002.000",
        "192.168.001.001",
        "255.255.255.255",
        # IPv6 full
        "2001:0db8:0000:0000:0000:ff00:0042:8329",
        # IPv6 compressed
        "2001:db8::",
        "2001:db8::1",
        "2001:db8::1:2:3:4:5:6",
        # IPv6 with embedded IPv4 (dual-stack)
        "2001:db8::192.0.2.33",
        "2001:db8:0:0:0:0:192.0.2.33",
        "::192.0.2.33",
        "::ffff:192.0.2.1",
        # IPv4 prefix
        "192.168.1.0/24",
        "0.0.0.0/0",
        # IPv4 range
        "192.0.2.80-192.0.2.85",
        "192.0.2.170-175",
        # IPv4 bracket
        "192.0.2.8[0-5]",
        "21.43.180.1[40-99]",
        "192.0.2.[5678]",
        # IPv4 Wildcard
        "15.63.148.*",
        # IPv6 Prefix
        "2001:0db8:0000:0000:0000:ff00:0042:8329/128",
        # IPv6 range
        "2001:db8::-2001:db8::ff",
    ]

    for ip in test_inputs:
        print("=" * 50)
        print("Input:", ip)
        ast = parse_ip_expr(ip)
        print("AST:", ast)
