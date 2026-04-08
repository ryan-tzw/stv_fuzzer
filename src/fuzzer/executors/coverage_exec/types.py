"""Shared type definitions for coverage executor payloads."""

from typing import NotRequired, TypedDict


class BranchStatEntry(TypedDict):
    line: int
    exits: int
    taken: int


class CoverageEntry(TypedDict):
    lines: list[int]
    arcs: list[list[int]]
    branch_stats: NotRequired[list[BranchStatEntry]]


CoveragePayload = dict[str, CoverageEntry]
