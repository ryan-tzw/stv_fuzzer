"""
Grammar-based seed generator using Grammarinator.
"""

import importlib.util
import inspect
from pathlib import Path


class GrammarSeedGenerator:
    """Dynamically loads Grammarinator classes to generate valid initial seeds."""

    def __init__(self, target: str, generator_dir: str | Path):
        self.target = target.lower()
        self.generator_dir = Path(generator_dir).resolve()

        self.prefix = self._discover_prefix()
        module_path = self.generator_dir / f"{self.prefix}Generator.py"

        if not module_path.exists():
            raise FileNotFoundError(f"Generator file not found: {module_path}")
        spec = importlib.util.spec_from_file_location(
            f"{self.prefix}Generator", module_path
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load module from {module_path}")

        generator_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generator_mod)

        self.GeneratorClass = getattr(generator_mod, f"{self.prefix}Generator")

        self.generator = self.GeneratorClass()
        self.start_rule = self._infer_start_rule()

    def _discover_prefix(self) -> str:
        """Finds the correct case-sensitive prefix by looking at the filesystem."""
        for file in self.generator_dir.glob("*Generator.py"):
            prefix = file.name.replace("Generator.py", "")
            if prefix.lower() == self.target:
                return prefix

        raise ValueError(f"No generator grammar found matching target: {self.target}")

    def _infer_start_rule(self) -> str:
        """Identify the start rule in the generated class."""
        for name, obj in self.GeneratorClass.__dict__.items():
            if (
                inspect.isfunction(obj)
                and not name.startswith("_")
                and name != "max_depth"
            ):
                print(name)
                return name

        raise AttributeError(f"Could not identify a start rule for {self.target}")

    def generate(self, count: int = 10) -> list[str]:
        """
        Generate syntactically valid inputs based on the target grammar.
        """
        rule = getattr(self.generator, self.start_rule)

        seeds = []
        for _ in range(count):
            tree = rule()
            seeds.append(str(tree))

        return seeds


if __name__ == "__main__":
    GENERATOR_DIR = (Path(__file__).parent).resolve()

    print("JSON Seeds:")
    json_gen = GrammarSeedGenerator("json", GENERATOR_DIR)
    for seed in json_gen.generate(count=2):
        print(f"  {seed}")

    print("\nIP Seeds:")
    ip_gen = GrammarSeedGenerator("ip", GENERATOR_DIR)
    for seed in ip_gen.generate(count=2):
        print(f"  {seed}")
