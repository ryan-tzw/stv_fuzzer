"""
Rich-based live dashboard for the fuzzing engine.

Usage:
    logger = FuzzerLogger(run_dir=..., config=...)
    with logger:
        logger.start(corpus_size=n, executions=0, cycles=0)
        # in loop:
        logger.tick(executions, cycles)
        logger.log_corpus_add(execution, cycle)
        logger.log_crash(execution, cycle, unique_crashes)
        logger.log_duplicate_crash(execution, cycle)
    logger.print_summary(executions, cycles, elapsed)
"""

import json
import os
import time
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

from rich.columns import Columns
from rich.console import Console, ConsoleOptions, RenderResult
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from fuzzer.config import FuzzerConfig


@dataclass
class FuzzerState:
    execution: int = 0
    cycle: int = 0
    corpus_size: int = 0
    unique_crashes: int = 0
    line_coverage: int = 0
    branch_coverage: int = 0
    arc_coverage: int = 0
    start_time: float | None = None
    events: list[Text] = field(default_factory=list)

    def elapsed_str(self) -> str:
        if self.start_time is None:
            return "00:00:00"
        secs = int(time.monotonic() - self.start_time)
        return str(timedelta(seconds=secs))

    def execs_per_s(self) -> float:
        if self.start_time is None:
            return 0.0
        elapsed = time.monotonic() - self.start_time
        return self.execution / elapsed if elapsed > 0 else 0.0


class FuzzerDisplay:
    def __init__(self, run_dir: Path, config: FuzzerConfig, state: FuzzerState):
        self._run_dir = run_dir
        self._config = config
        self._state = state

    def render_header(self) -> Panel:
        max_cycles = (
            str(self._config.max_cycles)
            if self._config.max_cycles is not None
            else "disabled"
        )
        time_limit = (
            f"{self._config.time_limit}s"
            if self._config.time_limit is not None
            else "disabled"
        )

        grid = Table.grid(padding=(0, 2))
        grid.add_column(style="bold cyan", min_width=16)
        grid.add_column()
        grid.add_row("Run dir:", str(self._run_dir))
        grid.add_row("Project:", str(self._config.project_dir))
        grid.add_row("Harness:", self._config.harness)
        grid.add_row(
            "Stop conditions:",
            f"max_cycles={max_cycles}  time_limit={time_limit}",
        )
        grid.add_row("Scheduler:", self._config.scheduler)
        return Panel(
            grid, title="[bold blue]STV Fuzzer[/bold blue]", border_style="blue"
        )

    def render_stats(self) -> Panel:
        grid = Table.grid(padding=(0, 3))
        grid.add_column(style="bold", min_width=18)
        grid.add_column(justify="right", style="bright_white")
        grid.add_row("Cycles:", str(self._state.cycle))
        grid.add_row("Executions:", str(self._state.execution))
        grid.add_row("Corpus size:", str(self._state.corpus_size))
        grid.add_row("Unique crashes:", str(self._state.unique_crashes))
        grid.add_row("Line coverage:", str(self._state.line_coverage))
        grid.add_row("Branch coverage:", str(self._state.branch_coverage))
        grid.add_row("Arc coverage:", str(self._state.arc_coverage))
        grid.add_row("Elapsed:", self._state.elapsed_str())
        grid.add_row("Exec/s:", f"{self._state.execs_per_s():.1f}")
        return Panel(grid, title="[bold green]Stats[/bold green]", border_style="green")

    def render_events(self) -> Panel:
        body = Text()
        for entry in self._state.events:
            body.append_text(entry)
            body.append("\n")
        return Panel(
            body,
            title="[bold yellow]Events[/bold yellow]",
            border_style="yellow",
        )

    def render_body(self) -> Columns:
        return Columns([self.render_stats(), self.render_events()], expand=True)


class FuzzerLogger:
    _MAX_EVENTS = 4

    def __init__(self, run_dir: Path, config: FuzzerConfig) -> None:
        self._run_dir = run_dir
        self._config = config
        self._console = Console()
        self._state = FuzzerState()
        self._display = FuzzerDisplay(run_dir, config, self._state)
        status_file = os.environ.get("STV_FUZZER_STATUS_FILE")
        self._status_file = Path(status_file).resolve() if status_file else None

        self._live = Live(
            self,
            console=self._console,
            refresh_per_second=4,
            vertical_overflow="visible",
        )

    # ------------------------------------------------------------------
    # Context manager — wraps Live
    # ------------------------------------------------------------------

    def __enter__(self) -> "FuzzerLogger":
        self._live.__enter__()
        return self

    def __exit__(self, *args) -> None:
        self._live.__exit__(*args)

    # ------------------------------------------------------------------
    # Rich renderable protocol
    # ------------------------------------------------------------------

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        yield self._display.render_header()
        yield self._display.render_body()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(
        self,
        corpus_size: int,
        executions: int = 0,
        cycles: int = 0,
        line_coverage: int = 0,
        branch_coverage: int = 0,
        arc_coverage: int = 0,
    ) -> None:
        """Call once before entering the fuzzing loop."""
        self._state.start_time = time.monotonic()
        self._state.corpus_size = corpus_size
        self._state.execution = executions
        self._state.cycle = cycles
        self._state.line_coverage = line_coverage
        self._state.branch_coverage = branch_coverage
        self._state.arc_coverage = arc_coverage
        self._write_status(running=True)

    def tick(
        self,
        executions: int,
        cycles: int,
        line_coverage: int = 0,
        branch_coverage: int = 0,
        arc_coverage: int = 0,
    ) -> None:
        """Call after each execution and cycle transition to keep counters current."""
        self._state.execution = executions
        self._state.cycle = cycles
        self._state.line_coverage = line_coverage
        self._state.branch_coverage = branch_coverage
        self._state.arc_coverage = arc_coverage
        self._write_status(running=True)

    def log_corpus_add(self, execution: int, cycle: int) -> None:
        self._state.execution = execution
        self._state.cycle = cycle
        self._state.corpus_size += 1
        self._push_event(
            f"[cycle {cycle} | exec {execution}] New coverage — corpus size: {self._state.corpus_size}",
            style="green",
        )
        self._write_status(running=True)

    def log_crash(self, execution: int, cycle: int, unique_crashes: int) -> None:
        self._state.execution = execution
        self._state.cycle = cycle
        self._state.unique_crashes = unique_crashes
        self._push_event(
            f"[cycle {cycle} | exec {execution}] New unique crash! Total unique: {unique_crashes}",
            style="bold red",
        )
        self._write_status(running=True)

    def log_duplicate_crash(self, execution: int, cycle: int) -> None:
        self._state.execution = execution
        self._state.cycle = cycle
        self._push_event(
            f"[cycle {cycle} | exec {execution}] Duplicate crash (not recorded again)",
            style="dim red",
        )
        self._write_status(running=True)

    def log_stop_reason(self, reason: str) -> None:
        self._push_event(f"Stopped — {reason}", style="bold yellow")
        self._write_status(running=True, stop_reason=reason)

    def print_summary(self, executions: int, cycles: int, elapsed: float) -> None:
        """Print a final summary below the dashboard after Live exits."""
        elapsed_str = str(timedelta(seconds=int(elapsed)))
        self._console.print()
        self._console.rule("[bold]Run complete[/bold]")
        summary = Table.grid(padding=(0, 2))
        summary.add_column(style="bold")
        summary.add_column(style="cyan")
        summary.add_row("Cycles:", str(cycles))
        summary.add_row("Executions:", str(executions))
        summary.add_row("Corpus size:", str(self._state.corpus_size))
        summary.add_row("Unique crashes:", str(self._state.unique_crashes))
        summary.add_row("Line coverage:", str(self._state.line_coverage))
        summary.add_row("Branch coverage:", str(self._state.branch_coverage))
        summary.add_row("Arc coverage:", str(self._state.arc_coverage))
        summary.add_row("Elapsed:", elapsed_str)
        summary.add_row("Results:", str(self._run_dir / "results.db"))
        self._console.print(summary)
        self._write_status(running=False)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _push_event(self, message: str, style: str = "") -> None:
        t = Text(message, style=style)
        self._state.events.append(t)
        if len(self._state.events) > self._MAX_EVENTS:
            self._state.events.pop(0)

    def _write_status(self, running: bool, stop_reason: str | None = None) -> None:
        if self._status_file is None:
            return

        payload = {
            "cycle": self._state.cycle,
            "execution": self._state.execution,
            "corpus_size": self._state.corpus_size,
            "unique_crashes": self._state.unique_crashes,
            "line_coverage": self._state.line_coverage,
            "branch_coverage": self._state.branch_coverage,
            "arc_coverage": self._state.arc_coverage,
            "execs_per_s": round(self._state.execs_per_s(), 2),
            "elapsed_s": int(
                time.monotonic() - (self._state.start_time or time.monotonic())
            ),
            "running": running,
            "stop_reason": stop_reason,
        }

        self._status_file.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._status_file.with_suffix(self._status_file.suffix + ".tmp")
        temp_path.write_text(json.dumps(payload), encoding="utf-8")
        temp_path.replace(self._status_file)
