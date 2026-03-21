import argparse
from pathlib import Path

from fuzzer.config import CORPUS_DIR, HARNESSES_DIR, FuzzerConfig
from fuzzer.core.mutator import AVAILABLE_STRATEGIES
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

    # Mutation
    parser.add_argument(
        "--mutation-strategy",
        choices=AVAILABLE_STRATEGIES,
        default=None,
        help=f"Mutation strategy (default: {FuzzerConfig.mutation_strategy})",
    )

    args = parser.parse_args()

    max_iterations = None if args.max_iterations == -1 else args.max_iterations
    time_limit = None if args.time_limit == -1 else args.time_limit

    # Build config in one pass so __post_init__ normalization/validation applies
    # to both defaults and CLI overrides.
    config = FuzzerConfig(
        project_dir=args.project_dir,
        harness=args.harness,
        corpus=args.corpus,
        runs_dir=args.runs_dir if args.runs_dir is not None else FuzzerConfig.runs_dir,
        max_iterations=(
            max_iterations
            if max_iterations is not None
            else FuzzerConfig.max_iterations
        ),
        time_limit=time_limit if time_limit is not None else FuzzerConfig.time_limit,
        scheduler=args.scheduler
        if args.scheduler is not None
        else FuzzerConfig.scheduler,
        mutation_strategy=(
            args.mutation_strategy
            if args.mutation_strategy is not None
            else FuzzerConfig.mutation_strategy
        ),
        energy_c=args.energy_c if args.energy_c is not None else FuzzerConfig.energy_c,
        max_energy=(
            args.max_energy if args.max_energy is not None else FuzzerConfig.max_energy
        ),
    )

    FuzzingEngine(config).run()
    return 0
