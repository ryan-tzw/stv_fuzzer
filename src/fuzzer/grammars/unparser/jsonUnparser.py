from .baseUnparser import Unparser


class jsonUnparser(Unparser):
    def unparse(self, node):
        t = node.type

        if t == "Object":
            pairs = [self.unparse(c) for c in node.children]
            return "{" + ", ".join(pairs) + "}"

        if t == "Pair":
            key = node.children[0].value
            value = self.unparse(node.children[1])
            return f'"{key}": {value}'

        if t == "Array":
            items = [self.unparse(c) for c in node.children]
            return "[" + ", ".join(items) + "]"

        if t == "String":
            return f'"{node.value}"'

        if t == "Number":
            return node.value

        if t == "Boolean":
            return "true" if node.value else "false"

        if t == "Null":
            return "null"

        return ""
