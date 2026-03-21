import argparse
from pathlib import Path

from fuzzer.config import CORPUS_DIR, HARNESSES_DIR, FuzzerConfig
from fuzzer.engine import FuzzingEngine


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="fuzzer",
        description="STV Fuzzer",
    )

    # Required
    parser.add_argument("project_dir", type=Path, help="Path to target uv directory")
    parser.add_argument(
        "harness",
        help=f"Harness name (resolved from {HARNESSES_DIR})",
    )
    parser.add_argument(
        "corpus",
        help=f"Corpus type name (resolved from {CORPUS_DIR})",
    )

    # Output
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=None,
        help=f"Directory to write run output to (default: {FuzzerConfig.runs_dir})",
    )

    # Stopping conditions
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help=f"Max number of iterations (-1 to disable, default: {FuzzerConfig.max_iterations})",
    )
    parser.add_argument(
        "--time-limit",
        type=int,
        default=None,
        help=f"Time limit in seconds (-1 to disable, default: {FuzzerConfig.time_limit})",
    )

    # Grammar
    parser.add_argument(
        "--grammar",
        choices=["json", "ip"],
        default=None,
        help=f"Grammar for generating syntactically valid inputs and performing structure-aware mutations. (default: {FuzzerConfig.grammar})",
    )
    parser.add_argument(
        "--mutate-depth",
        type=int,
        default=1,
        help=f"Number of stacked mutations per generated input (default: {FuzzerConfig.mutate_depth})",
    )

    # Scheduler
    parser.add_argument(
        "--scheduler",
        choices=["random", "fast"],
        default=None,
        help=f"Scheduling strategy (default: {FuzzerConfig.scheduler})",
    )
    parser.add_argument(
        "--energy-c",
        type=float,
        default=None,
        help=f"Base energy constant for FastScheduler (default: {FuzzerConfig.energy_c})",
    )
    parser.add_argument(
        "--max-energy",
        type=int,
        default=None,
        help=f"Max energy cap for FastScheduler (default: {FuzzerConfig.max_energy})",
    )

    args = parser.parse_args()

    # Start from config defaults, then apply any explicit CLI overrides
    config = FuzzerConfig(
        project_dir=args.project_dir,
        harness=args.harness,
        corpus=args.corpus,
    )
    if args.runs_dir is not None:
        config.runs_dir = args.runs_dir
    if args.max_iterations is not None:
        config.max_iterations = args.max_iterations
    if args.time_limit is not None:
        config.time_limit = args.time_limit
    if args.grammar is not None:
        config.grammar = args.grammar
    if args.mutate_depth is not None:
        config.mutate_depth = args.mutate_depth
    if args.scheduler is not None:
        config.scheduler = args.scheduler
    if args.energy_c is not None:
        config.energy_c = args.energy_c
    if args.max_energy is not None:
        config.max_energy = args.max_energy

    FuzzingEngine(config).run()
    return 0
