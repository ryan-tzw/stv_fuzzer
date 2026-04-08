import argparse
from pathlib import Path

from fuzzer.config import (
    CORPUS_DIR,
    HARNESSES_DIR,
    FuzzerConfig,
    available_profiles,
    profile_overrides,
)
from fuzzer.mutator import AVAILABLE_STRATEGIES
from fuzzer.engine import FuzzingEngine
from fuzzer.parallel import run_parallel, run_parallel_profiles


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="fuzzer",
        description="STV Fuzzer",
    )

    profile_choices = list(available_profiles())

    # Profile-first configuration
    parser.add_argument(
        "--profile",
        choices=profile_choices,
        default=None,
        help="Built-in target profile to load as base configuration",
    )
    parser.add_argument(
        "--profiles",
        default=None,
        help="Comma-separated built-in profiles for concurrent multi-profile runs",
    )
    parser.add_argument(
        "--list-profiles",
        action="store_true",
        help="List available built-in profiles and exit",
    )

    # Target (named flags only; profile can provide defaults)
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=None,
        help="Path to target uv directory",
    )
    parser.add_argument(
        "--harness",
        default=None,
        help=f"Harness name (resolved from {HARNESSES_DIR})",
    )
    parser.add_argument(
        "--corpus",
        default=None,
        help=f"Corpus type name (resolved from {CORPUS_DIR})",
    )

    # Pipeline mode
    parser.add_argument(
        "--mode",
        choices=["coverage", "differential"],
        default=None,
        help=f"Execution mode (default: {FuzzerConfig.mode})",
    )

    # Harness args
    parser.add_argument(
        "--harness-arg",
        action="append",
        default=None,
        help="Extra argument passed to the harness (repeatable)",
    )

    # Differential blackbox options
    parser.add_argument(
        "--blackbox-binary",
        type=Path,
        default=None,
        help="Path to blackbox target binary (required in differential mode)",
    )
    parser.add_argument(
        "--blackbox-input-flag",
        default=None,
        help=f"Input flag for blackbox binary (default: {FuzzerConfig.blackbox_input_flag})",
    )
    parser.add_argument(
        "--blackbox-arg",
        action="append",
        default=None,
        help="Static argument passed to blackbox binary (repeatable)",
    )
    parser.add_argument(
        "--blackbox-timeout",
        type=float,
        default=None,
        help=(
            "Timeout in seconds for blackbox binary execution "
            f"(-1 to disable, default: {FuzzerConfig.blackbox_timeout})"
        ),
    )

    # Output
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=None,
        help=f"Directory to write run output to (default: {FuzzerConfig.runs_dir})",
    )
    parser.add_argument(
        "--parallel-workers",
        type=int,
        default=1,
        help="Number of parallel worker processes (default: 1)",
    )

    # Stopping conditions
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=None,
        help=f"Max number of cycles (-1 to disable, default: {FuzzerConfig.max_cycles})",
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
    if args.parallel_workers < 1:
        parser.error("--parallel-workers must be >= 1")
    if args.profile is not None and args.profiles is not None:
        parser.error("--profile and --profiles cannot be used together")

    if args.list_profiles:
        for name in profile_choices:
            print(name)
        return 0

    max_cycles_arg = None if args.max_cycles == -1 else args.max_cycles
    time_limit = None if args.time_limit == -1 else args.time_limit

    if args.profiles is not None:
        profile_names = [p.strip() for p in args.profiles.split(",") if p.strip()]
        if not profile_names:
            parser.error("--profiles must include at least one profile name")

        invalid = [p for p in profile_names if p not in profile_choices]
        if invalid:
            parser.error(f"Unknown profile(s): {', '.join(invalid)}")

        if args.parallel_workers < len(profile_names):
            parser.error("--parallel-workers must be >= number of profiles")

        if (
            args.project_dir is not None
            or args.harness is not None
            or args.corpus is not None
            or args.mode is not None
            or args.harness_arg is not None
            or args.blackbox_binary is not None
            or args.blackbox_input_flag is not None
            or args.blackbox_arg is not None
            or args.blackbox_timeout is not None
        ):
            parser.error(
                "target-specific overrides are not supported with --profiles; "
                "use profile defaults only"
            )

        configs: list[FuzzerConfig] = []
        for profile_name in profile_names:
            base = profile_overrides(profile_name)
            configs.append(
                FuzzerConfig(
                    project_dir=base["project_dir"],
                    harness=base["harness"],
                    corpus=base["corpus"],
                    mode=base.get("mode", FuzzerConfig.mode),
                    harness_args=tuple(
                        base.get("harness_args", FuzzerConfig.harness_args)
                    ),
                    blackbox_binary=base.get("blackbox_binary"),
                    blackbox_input_flag=base.get(
                        "blackbox_input_flag",
                        FuzzerConfig.blackbox_input_flag,
                    ),
                    blackbox_args=tuple(
                        base.get("blackbox_args", FuzzerConfig.blackbox_args)
                    ),
                    blackbox_timeout=base.get(
                        "blackbox_timeout", FuzzerConfig.blackbox_timeout
                    ),
                    runs_dir=(
                        args.runs_dir
                        if args.runs_dir is not None
                        else base.get("runs_dir", FuzzerConfig.runs_dir)
                    ),
                    max_cycles=(
                        max_cycles_arg
                        if max_cycles_arg is not None
                        else base.get("max_cycles", FuzzerConfig.max_cycles)
                    ),
                    time_limit=(
                        time_limit
                        if time_limit is not None
                        else base.get("time_limit", FuzzerConfig.time_limit)
                    ),
                    scheduler=(
                        args.scheduler
                        if args.scheduler is not None
                        else base.get("scheduler", FuzzerConfig.scheduler)
                    ),
                    mutation_strategy=(
                        args.mutation_strategy
                        if args.mutation_strategy is not None
                        else base.get(
                            "mutation_strategy", FuzzerConfig.mutation_strategy
                        )
                    ),
                    energy_c=(
                        args.energy_c
                        if args.energy_c is not None
                        else base.get("energy_c", FuzzerConfig.energy_c)
                    ),
                    max_energy=(
                        args.max_energy
                        if args.max_energy is not None
                        else base.get("max_energy", FuzzerConfig.max_energy)
                    ),
                )
            )

        return run_parallel_profiles(configs, args.parallel_workers, profile_names)

    base = profile_overrides(args.profile) if args.profile is not None else {}

    project_dir = (
        args.project_dir if args.project_dir is not None else base.get("project_dir")
    )
    harness = args.harness if args.harness is not None else base.get("harness")
    corpus = args.corpus if args.corpus is not None else base.get("corpus")

    if project_dir is None:
        parser.error("Missing --project-dir (or set it in --profile)")
    if harness is None:
        parser.error("Missing --harness (or set it in --profile)")
    if corpus is None:
        parser.error("Missing --corpus (or set it in --profile)")

    # Build config in one pass so __post_init__ normalization/validation applies
    # to both defaults and CLI overrides.
    config = FuzzerConfig(
        project_dir=project_dir,
        harness=harness,
        corpus=corpus,
        mode=args.mode
        if args.mode is not None
        else base.get("mode", FuzzerConfig.mode),
        harness_args=(
            tuple(args.harness_arg)
            if args.harness_arg is not None
            else tuple(base.get("harness_args", FuzzerConfig.harness_args))
        ),
        blackbox_binary=(
            args.blackbox_binary
            if args.blackbox_binary is not None
            else base.get("blackbox_binary")
        ),
        blackbox_input_flag=(
            args.blackbox_input_flag
            if args.blackbox_input_flag is not None
            else base.get("blackbox_input_flag", FuzzerConfig.blackbox_input_flag)
        ),
        blackbox_args=(
            tuple(args.blackbox_arg)
            if args.blackbox_arg is not None
            else tuple(base.get("blackbox_args", FuzzerConfig.blackbox_args))
        ),
        blackbox_timeout=(
            args.blackbox_timeout
            if args.blackbox_timeout is not None
            else base.get("blackbox_timeout", FuzzerConfig.blackbox_timeout)
        ),
        runs_dir=(
            args.runs_dir
            if args.runs_dir is not None
            else base.get("runs_dir", FuzzerConfig.runs_dir)
        ),
        max_cycles=(
            max_cycles_arg
            if max_cycles_arg is not None
            else base.get("max_cycles", FuzzerConfig.max_cycles)
        ),
        time_limit=(
            time_limit
            if time_limit is not None
            else base.get("time_limit", FuzzerConfig.time_limit)
        ),
        scheduler=args.scheduler
        if args.scheduler is not None
        else base.get("scheduler", FuzzerConfig.scheduler),
        mutation_strategy=(
            args.mutation_strategy
            if args.mutation_strategy is not None
            else base.get("mutation_strategy", FuzzerConfig.mutation_strategy)
        ),
        energy_c=(
            args.energy_c
            if args.energy_c is not None
            else base.get("energy_c", FuzzerConfig.energy_c)
        ),
        max_energy=(
            args.max_energy
            if args.max_energy is not None
            else base.get("max_energy", FuzzerConfig.max_energy)
        ),
    )

    if args.parallel_workers > 1:
        return run_parallel(config, args.parallel_workers)

    FuzzingEngine(config).run()
    return 0
