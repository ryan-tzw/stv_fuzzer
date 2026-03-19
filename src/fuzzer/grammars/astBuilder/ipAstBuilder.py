from ..antlr.ip.ipVisitor import ipVisitor
from ..antlr.ip.ipParser import ipParser
from .astNode import AstNode
from antlr4 import TerminalNode


class ipAstBuilder(ipVisitor):
    """
    Build a compact AST for the NEW ip grammar (the version with ipAddress root,
    ipv4Address/ipv4Octet, h16, ls32, and the detailed ipv6Address alternatives).

    Produced node types (kept compatible with previous expectations):
      - Ipv4 (children = Octet nodes)
      - Octet (value = string, e.g. "192" or "001")
      - Ipv6Full / Ipv6Compressed (children = H16 / DoubleColon / Ipv4 nodes)
      - H16 (value = string)
      - DoubleColon (value = "::")
      - Ipv4 (nested when used as IPv4-mapped/dual-stack suffix)

    Compression (::) is detected automatically even though the grammar uses two COLON tokens.
    Textual fidelity for IPv6 is preserved via structured children instead of raw getText().
    """

    # ================= ROOT =================
    def visitIpAddress(self, ctx: ipParser.IpAddressContext):
        """Entry point - matches the root rule of the new grammar."""
        if ctx.ipv4Address():
            return self.visit(ctx.ipv4Address())
        if ctx.ipv6Address():
            return self.visit(ctx.ipv6Address())
        return AstNode("Ip", value=ctx.getText())

    # ================= IPv4 =================
    def visitIpv4Address(self, ctx: ipParser.Ipv4AddressContext):
        octets = [self.visit(o) for o in ctx.ipv4Octet()]
        return AstNode("Ipv4", children=octets)

    def visitIpv4Octet(self, ctx: ipParser.Ipv4OctetContext):
        return AstNode("Octet", value=ctx.getText())

    # ================= IPv6 =================
    def visitIpv6Address(self, ctx: ipParser.Ipv6AddressContext):
        """
        Unified handler for ALL IPv6 forms (full + every compressed variant).
        Builds the same Ipv6Full / Ipv6Compressed structure as the old builder.
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
                    # single ":" → skip (as in the old builder)
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

        # Decide node type exactly like the old builder
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
        # Otherwise it's the h16 ":" h16 alternative
        return [self.visit(h) for h in ctx.h16()]

    # ================= HELPERS (kept for compatibility) =================
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

        # CHANGED: new grammar root is ipAddress (was ip_item)
        tree = parser.ipAddress()
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
    ]

    for ip in test_inputs:
        print("=" * 50)
        print("Input:", ip)
        ast = parse_ip_expr(ip)
        print("AST:", ast)
