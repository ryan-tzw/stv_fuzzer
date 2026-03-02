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
from datetime import timedelta
from pathlib import Path

from rich.columns import Columns
from rich.console import Console, ConsoleOptions, RenderResult
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from fuzzer.config import FuzzerConfig


class FuzzerLogger:
    _MAX_EVENTS = 4

    def __init__(self, run_dir: Path, config: FuzzerConfig) -> None:
        self._run_dir = run_dir
        self._config = config
        self._console = Console()

        # Live state
        self._iteration: int = 0
        self._corpus_size: int = 0
        self._unique_crashes: int = 0
        self._start_time: float | None = None
        self._events: list[Text] = []

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
        yield self._build_header()
        yield self._build_body()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self, corpus_size: int) -> None:
        """Call once before entering the fuzzing loop."""
        self._start_time = time.monotonic()
        self._corpus_size = corpus_size

    def tick(self, iteration: int) -> None:
        """Call each iteration to keep the iteration counter current."""
        self._iteration = iteration

    def log_corpus_add(self, iteration: int) -> None:
        self._iteration = iteration
        self._corpus_size += 1
        self._push_event(
            f"[iter {iteration}] New coverage — corpus size: {self._corpus_size}",
            style="green",
        )

    def log_crash(self, iteration: int, unique_crashes: int) -> None:
        self._iteration = iteration
        self._unique_crashes = unique_crashes
        self._push_event(
            f"[iter {iteration}] New unique crash! Total unique: {unique_crashes}",
            style="bold red",
        )

    def log_duplicate_crash(self, iteration: int) -> None:
        self._iteration = iteration
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
        summary.add_row("Corpus size:", str(self._corpus_size))
        summary.add_row("Unique crashes:", str(self._unique_crashes))
        summary.add_row("Elapsed:", elapsed_str)
        summary.add_row("Results:", str(self._run_dir / "results.db"))
        self._console.print(summary)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _push_event(self, message: str, style: str = "") -> None:
        t = Text(message, style=style)
        self._events.append(t)
        if len(self._events) > self._MAX_EVENTS:
            self._events.pop(0)

    def _elapsed_str(self) -> str:
        if self._start_time is None:
            return "00:00:00"
        secs = int(time.monotonic() - self._start_time)
        return str(timedelta(seconds=secs))

    def _execs_per_s(self) -> float:
        if self._start_time is None:
            return 0.0
        elapsed = time.monotonic() - self._start_time
        return self._iteration / elapsed if elapsed > 0 else 0.0

    # --- Panels --------------------------------------------------------

    def _build_header(self) -> Panel:
        grid = Table.grid(padding=(0, 2))
        grid.add_column(style="bold cyan", min_width=16)
        grid.add_column()
        grid.add_row("Run dir:", str(self._run_dir))
        grid.add_row("Project:", str(self._config.project_dir))
        grid.add_row("Harness:", self._config.harness)
        grid.add_row(
            "Stop conditions:",
            f"max_iterations={self._config.max_iterations}  "
            f"time_limit={self._config.time_limit}s",
        )
        grid.add_row("Scheduler:", self._config.scheduler)
        return Panel(
            grid, title="[bold blue]STV Fuzzer[/bold blue]", border_style="blue"
        )

    def _build_stats(self) -> Panel:
        grid = Table.grid(padding=(0, 3))
        grid.add_column(style="bold", min_width=18)
        grid.add_column(justify="right", style="bright_white")
        grid.add_row("Iterations:", str(self._iteration))
        grid.add_row("Corpus size:", str(self._corpus_size))
        grid.add_row("Unique crashes:", str(self._unique_crashes))
        grid.add_row("Elapsed:", self._elapsed_str())
        grid.add_row("Exec/s:", f"{self._execs_per_s():.1f}")
        return Panel(grid, title="[bold green]Stats[/bold green]", border_style="green")

    def _build_events(self) -> Panel:
        body = Text()
        for entry in self._events:
            body.append_text(entry)
            body.append("\n")
        return Panel(
            body,
            title="[bold yellow]Events[/bold yellow]",
            border_style="yellow",
        )

    def _build_body(self) -> Columns:
        return Columns([self._build_stats(), self._build_events()], expand=True)
