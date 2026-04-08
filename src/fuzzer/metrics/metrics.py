from dataclasses import dataclass


@dataclass
class MetricsSnapshot:
    timestamp: str
    corpus_size: int
    interesting_seed: int
    unique_crashes: int
    total_crashes: int
    line_coverage: int
    branch_coverage: int
    total_edges: int
    executions: int
    execs_per_sec: float
