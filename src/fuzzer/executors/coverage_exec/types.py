"""Shared type definitions for coverage executor payloads."""

from typing import TypedDict


class CoverageEntry(TypedDict):
    lines: list[int]
    arcs: list[list[int]]


CoveragePayload = dict[str, CoverageEntry]
