from .baseUnparser import Unparser


class ipUnparser(Unparser):
    def unparse(self, node):
        t = node.type

        # IPV4 Base
        if t == "Ipv4":
            return ".".join(self.unparse(c) for c in node.children)

        if t == "Octet":
            return node.value

        # IPv4 Extended Forms
        if t == "Ipv4Cidr":
            return f"{self.unparse(node.children[0])}/{self.unparse(node.children[1])}"

        if t in ("Ipv4Range", "Ipv4ShorthandRange"):
            return f"{self.unparse(node.children[0])}-{self.unparse(node.children[1])}"

        if t == "Ipv4Bracket":
            return f"{self.unparse(node.children[0])}[{self.unparse(node.children[1])}]"

        if t == "Ipv4BracketOctets":
            prefix = ".".join(self.unparse(c) for c in node.children[:3])
            content = self.unparse(node.children[3])
            return f"{prefix}.[{content}]"

        if t == "Ipv4Wildcard":
            prefix = ".".join(self.unparse(c) for c in node.children)
            return f"{prefix}.*"

        # IPv6 Base
        if t in ("Ipv6Full", "Ipv6Compressed"):
            parts = []
            for c in node.children:
                if c.type == "DoubleColon":
                    parts.append("::")
                else:
                    parts.append(self.unparse(c))
            # Join with ":" but avoid breaking "::"
            result = ""
            for i, p in enumerate(parts):
                if p == "::":
                    result += "::"
                else:
                    if result and not result.endswith(":"):
                        result += ":"
                    result += p
            return result

        if t == "H16":
            return node.value

        if t == "DoubleColon":
            return "::"

        # IPv6 Extended Forms
        if t == "Ipv6Cidr":
            return f"{self.unparse(node.children[0])}/{self.unparse(node.children[1])}"

        if t == "Ipv6Range":
            return f"{self.unparse(node.children[0])}-{self.unparse(node.children[1])}"

        # Shared Leaf Nodes
        if t in ("PrefixV4", "PrefixV6", "BracketContent"):
            return node.value

        # Fallback
        if node.children:
            return "".join(self.unparse(c) for c in node.children)

        if node.value:
            return node.value

        return ""
