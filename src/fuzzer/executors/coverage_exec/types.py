"""Shared type definitions for coverage executor payloads."""

from typing import NotRequired, TypedDict


class BranchStatEntry(TypedDict):
    line: int
    exits: int
    taken: int


class CoverageEntry(TypedDict):
    lines: list[int]
    arcs: list[list[int]]
    branch_decision_lines: NotRequired[list[int]]
    # Legacy compatibility field; newer workers emit branch_decision_lines.
    branch_stats: NotRequired[list[BranchStatEntry]]


CoveragePayload = dict[str, CoverageEntry]
