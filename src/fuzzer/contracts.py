"""Runtime contracts for engine-wired observer/feedback components."""

from typing import Protocol, TypeVar, runtime_checkable

from fuzzer.observers.input import ObservationInput, ParsedCrash


SignalOutT = TypeVar("SignalOutT", covariant=True)
SignalInT = TypeVar("SignalInT", contravariant=True)


class ObserverProtocol(Protocol[SignalOutT]):
    """Minimum observer contract required by the engine."""

    def observe(self, execution: ObservationInput) -> SignalOutT:
        """Parse raw execution data into a signal object."""
        ...


class FeedbackProtocol(Protocol[SignalInT]):
    """Minimum feedback contract required by the engine."""

    def evaluate(self, signal: SignalInT) -> bool:
        """Return True when the input should be added to corpus."""
        ...


@runtime_checkable
class SupportsCycleStart(Protocol):
    """Optional feedback capability: cycle-boundary callback."""

    def on_cycle_start(self, cycle: int) -> None:
        """Notify feedback when a new cycle starts."""
        ...


@runtime_checkable
class CoverageStatsProvider(Protocol):
    """Optional feedback capability: cumulative coverage counters."""

    @property
    def total_seen_lines(self) -> int: ...

    @property
    def total_seen_branches(self) -> int: ...

    @property
    def total_seen_arcs(self) -> int: ...


@runtime_checkable
class CrashSignalProtocol(Protocol):
    """Optional signal capability: parsed crash metadata."""

    @property
    def parsed_crash(self) -> ParsedCrash | None: ...
