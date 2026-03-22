"""
Custom ANTLR-based seed generator.
"""

import importlib.util
from pathlib import Path


class GrammarSeedGenerator:
    """Dynamically loads custom Generator classes to produce valid initial seeds."""

    def __init__(self, target: str, generator_dir: str | Path, **kwargs):
        self.target = target.lower()
        self.generator_dir = Path(generator_dir).resolve()

        module_path = self.generator_dir / f"{self.target}Generator.py"

        if not module_path.exists():
            raise FileNotFoundError(f"Generator file not found: {module_path}")

        spec = importlib.util.spec_from_file_location(
            f"{self.target}Generator", module_path
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load module from {module_path}")

        generator_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generator_mod)

        self.GeneratorClass = getattr(generator_mod, f"{self.target}Generator")

        self.generator = self.GeneratorClass(**kwargs)

    def generate(self, count: int = 10) -> list[str]:
        """
        Generate syntactically valid inputs based on the target grammar.
        """
        seeds = []
        for _ in range(count):
            seed = self.generator.generate()
            seeds.append(str(seed))

        return seeds


if __name__ == "__main__":
    GENERATOR_DIR = (Path(__file__).parent).resolve()

    print("JSON Seeds:")
    json_gen = GrammarSeedGenerator("json", GENERATOR_DIR, max_depth=3)
    for seed in json_gen.generate(count=2):
        print(f"  {seed}")

    print("\nIP Seeds:")
    ip_gen = GrammarSeedGenerator("ip", GENERATOR_DIR, mode="cidrize")
    for seed in ip_gen.generate(count=2):
        print(f"  {seed}")

    print("\nIP Seeds:")
    ip_gen = GrammarSeedGenerator("ip", GENERATOR_DIR, mode="parser")
    for seed in ip_gen.generate(count=2):
        print(f"  {seed}")
