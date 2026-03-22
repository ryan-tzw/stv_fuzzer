import random
import string

from fuzzer.grammars.antlr.json.jsonVisitor import jsonVisitor


class jsonGenerator(jsonVisitor):
    def __init__(self, max_depth=3):
        self.max_depth = max_depth
        self.current_depth = 0

    def generate(self):
        """Entry point to generate a random JSON string."""
        return self.visitJson(None)

    def visitJson(self, ctx):
        return self.visitValue(None)

    def visitValue(self, ctx):
        options = [
            self.visitString,
            self.visitNumber,
            self.visitTrueValue,
            self.visitFalseValue,
            self.visitNullValue,
        ]
        # Only allow nesting if we haven't hit max depth
        if self.current_depth < self.max_depth:
            options.extend([self.visitJsonObject, self.visitArray])
        choice = random.choice(options)
        return choice(None)

    def visitJsonObject(self, ctx):
        self.current_depth += 1
        num_members = random.randint(0, 5)
        members = [self.visitMember(None) for _ in range(num_members)]
        self.current_depth -= 1
        return "{" + ", ".join(members) + "}"

    def visitMember(self, ctx):
        key = self.visitString(None)
        val = self.visitValue(None)
        return f"{key}: {val}"

    def visitArray(self, ctx):
        self.current_depth += 1
        num_elements = random.randint(0, 5)
        elements = [self.visitValue(None) for _ in range(num_elements)]
        self.current_depth -= 1
        return "[" + ", ".join(elements) + "]"

    def visitString(self, ctx):
        length = random.randint(1, 10)
        chars = string.ascii_letters + string.digits
        random_str = "".join(random.choice(chars) for _ in range(length))
        return f'"{random_str}"'

    def visitNumber(self, ctx):
        if random.random() > 0.5:
            return str(random.randint(-1000, 1000))
        else:
            return f"{random.uniform(-1000, 1000):.2f}"

    def visitTrueValue(self, ctx):
        return "true"

    def visitFalseValue(self, ctx):
        return "false"

    def visitNullValue(self, ctx):
        return "null"


if __name__ == "__main__":
    gen = jsonGenerator(max_depth=5)
    for i in range(15):
        print(f"Sample {i + 1}: {gen.generate()}")
