"""
Rich-based live dashboard for the fuzzing engine.

Usage:
    logger = FuzzerLogger(run_dir=..., config=...)
    with logger:
        logger.start(corpus_size=n)
        # in loop:
        logger.tick(iteration)
        logger.log_corpus_add(iteration)
        logger.log_crash(iteration, unique_crashes)
        logger.log_duplicate_crash(iteration)
    logger.print_summary(iteration, elapsed)
"""

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
    iteration: int = 0
    corpus_size: int = 0
    unique_crashes: int = 0
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
        return self.iteration / elapsed if elapsed > 0 else 0.0


class FuzzerDisplay:
    def __init__(self, run_dir: Path, config: FuzzerConfig, state: FuzzerState):
        self._run_dir = run_dir
        self._config = config
        self._state = state

    def render_header(self) -> Panel:
        max_iterations = (
            str(self._config.max_iterations)
            if self._config.max_iterations is not None
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
            f"max_iterations={max_iterations}  time_limit={time_limit}",
        )
        grid.add_row("Scheduler:", self._config.scheduler)
        return Panel(
            grid, title="[bold blue]STV Fuzzer[/bold blue]", border_style="blue"
        )

    def render_stats(self) -> Panel:
        grid = Table.grid(padding=(0, 3))
        grid.add_column(style="bold", min_width=18)
        grid.add_column(justify="right", style="bright_white")
        grid.add_row("Iterations:", str(self._state.iteration))
        grid.add_row("Corpus size:", str(self._state.corpus_size))
        grid.add_row("Unique crashes:", str(self._state.unique_crashes))
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

    def start(self, corpus_size: int) -> None:
        """Call once before entering the fuzzing loop."""
        self._state.start_time = time.monotonic()
        self._state.corpus_size = corpus_size

    def tick(self, iteration: int) -> None:
        """Call each iteration to keep the iteration counter current."""
        self._state.iteration = iteration

    def log_corpus_add(self, iteration: int) -> None:
        self._state.iteration = iteration
        self._state.corpus_size += 1
        self._push_event(
            f"[iter {iteration}] New coverage — corpus size: {self._state.corpus_size}",
            style="green",
        )

    def log_crash(self, iteration: int, unique_crashes: int) -> None:
        self._state.iteration = iteration
        self._state.unique_crashes = unique_crashes
        self._push_event(
            f"[iter {iteration}] New unique crash! Total unique: {unique_crashes}",
            style="bold red",
        )

    def log_duplicate_crash(self, iteration: int) -> None:
        self._state.iteration = iteration
        self._push_event(
            f"[iter {iteration}] Duplicate crash (not recorded again)",
            style="dim red",
        )

    def log_stop_reason(self, reason: str) -> None:
        self._push_event(f"Stopped — {reason}", style="bold yellow")

    def print_summary(self, iteration: int, elapsed: float) -> None:
        """Print a final summary below the dashboard after Live exits."""
        elapsed_str = str(timedelta(seconds=int(elapsed)))
        self._console.print()
        self._console.rule("[bold]Run complete[/bold]")
        summary = Table.grid(padding=(0, 2))
        summary.add_column(style="bold")
        summary.add_column(style="cyan")
        summary.add_row("Iterations:", str(iteration))
        summary.add_row("Corpus size:", str(self._state.corpus_size))
        summary.add_row("Unique crashes:", str(self._state.unique_crashes))
        summary.add_row("Elapsed:", elapsed_str)
        summary.add_row("Results:", str(self._run_dir / "results.db"))
        self._console.print(summary)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _push_event(self, message: str, style: str = "") -> None:
        t = Text(message, style=style)
        self._state.events.append(t)
        if len(self._state.events) > self._MAX_EVENTS:
            self._state.events.pop(0)
