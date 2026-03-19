from .baseUnparser import Unparser


class ipUnparser(Unparser):
    def unparse(self, node):
        t = node.type

        # IPV4
        if t == "Ipv4":
            return ".".join(self.unparse(c) for c in node.children)

        if t == "Octet":
            return node.value

        # IPv6
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

        if node.value:
            return node.value

        # Fallback
        if node.children:
            return "".join(self.unparse(c) for c in node.children)

        if node.value:
            return node.value

        return ""
