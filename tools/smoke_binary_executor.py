"""Quick smoke-check for BinaryExecutor against blackbox Linux binaries.

This helper runs a few known-valid sample inputs through the packaged binaries
and prints each run result (exit code, stdout, stderr).
"""

import argparse
from dataclasses import dataclass
from pathlib import Path

from fuzzer.executors.differential.binary import BinaryExecutor


@dataclass(frozen=True)
class SmokeCase:
    name: str
    binary_path: Path
    sample_input: str
    static_args: tuple[str, ...] = ()


def _default_cases(repo_root: Path) -> list[SmokeCase]:
    return [
        SmokeCase(
            name="ipv4-parser",
            binary_path=repo_root
            / "targets"
            / "IPv4-IPv6-parser"
            / "bin"
            / "linux-ipv4-parser",
            sample_input="192.168.1.1",
        ),
        SmokeCase(
            name="ipv6-parser",
            binary_path=repo_root
            / "targets"
            / "IPv4-IPv6-parser"
            / "bin"
            / "linux-ipv6-parser",
            sample_input="2001:db8::1",
        ),
        SmokeCase(
            name="cidrize-runner",
            binary_path=repo_root
            / "targets"
            / "cidrize-runner"
            / "bin"
            / "linux-cidrize-runner",
            sample_input="1.2.3.4",
            static_args=("--func", "cidrize"),
        ),
    ]


def _run_case(case: SmokeCase, timeout: float) -> int:
    print(f"=== {case.name} ===")
    print(f"binary: {case.binary_path}")
    print(f"input:  {case.sample_input}")

    if not case.binary_path.exists():
        print("status: missing binary")
        print()
        return 2

    executor = BinaryExecutor(
        binary_path=case.binary_path,
        static_args=list(case.static_args),
        timeout=timeout,
    )
    result = executor.run(case.sample_input)

    print(f"exit_code: {result.exit_code}")
    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    print(f"stdout: {stdout if stdout else '<empty>'}")
    print(f"stderr: {stderr if stderr else '<empty>'}")
    print()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Smoke test BinaryExecutor with packaged Linux binaries"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Per-run timeout in seconds (default: 5.0)",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    cases = _default_cases(repo_root)

    statuses = [_run_case(case, timeout=args.timeout) for case in cases]

    if any(status == 2 for status in statuses):
        print("Finished with missing binaries.")
        return 2

    print("Smoke run complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
