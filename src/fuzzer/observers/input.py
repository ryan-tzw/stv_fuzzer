"""Observer input models.

These models decouple observer APIs from executor-specific return types.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ObservationInput:
    """Common execution fields made available to observers."""

    stdout: str
    stderr: str
    exit_code: int
    result: Any
