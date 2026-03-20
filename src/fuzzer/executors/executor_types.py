"""Shared type definitions for executor outputs."""

from dataclasses import dataclass, field
from typing import Literal, TypeAlias, TypedDict

RawArc: TypeAlias = tuple[int, int] | list[int]


class RawCoverageFile(TypedDict, total=False):
    """Raw per-file coverage payload emitted by coverage executors."""

    lines: list[int]
    arcs: list[RawArc]


RawCoverageMap: TypeAlias = dict[str, RawCoverageFile]

DiffKind: TypeAlias = Literal[
    "outcome_mismatch",
    "executor_failure",
]


@dataclass(slots=True)
class ExecutorResult:
    """Common execution result shape returned by all executors."""

    stdout: str
    stderr: str
    return_code: int
    raw_coverage: RawCoverageMap = field(default_factory=dict)
    is_diff: bool = False
    diff_kind: DiffKind | None = None
