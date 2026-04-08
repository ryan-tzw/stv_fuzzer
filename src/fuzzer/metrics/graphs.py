"""Matplotlib helpers for rendering telemetry time-series graphs."""

from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt


MetricSeries = list[tuple[str, int]]


def create_coverage_graph(data: MetricSeries, output_dir: Path) -> Path | None:
    """Render arc coverage over elapsed time."""
    return _plot_series(
        data=data,
        output_dir=output_dir,
        filename="coverage_over_time.png",
        title="Coverage Over Time",
        ylabel="Arc Coverage",
        color="tab:blue",
    )


def create_unique_crashes_graph(data: MetricSeries, output_dir: Path) -> Path | None:
    """Render unique crashes over elapsed time."""
    return _plot_series(
        data=data,
        output_dir=output_dir,
        filename="unique_crashes_over_time.png",
        title="Unique Crashes Over Time",
        ylabel="Unique Crashes",
        color="tab:red",
    )


def create_interesting_seed_graph(data: MetricSeries, output_dir: Path) -> Path | None:
    """Render interesting-seed count over elapsed time."""
    return _plot_series(
        data=data,
        output_dir=output_dir,
        filename="interesting_seeds_over_time.png",
        title="Interesting Seeds Over Time",
        ylabel="Interesting Seeds",
        color="tab:green",
    )


def _plot_series(
    *,
    data: MetricSeries,
    output_dir: Path,
    filename: str,
    title: str,
    ylabel: str,
    color: str,
) -> Path | None:
    normalised = _normalise_series(data)
    if normalised is None:
        return None
    elapsed_seconds, values = normalised

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename

    fig, ax = plt.subplots(figsize=(8.0, 4.5))
    ax.plot(
        elapsed_seconds,
        values,
        marker="o",
        linewidth=1.5,
        markersize=3,
        color=color,
    )
    ax.set_title(title)
    ax.set_xlabel("Elapsed Time (s)")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.35)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def _normalise_series(data: MetricSeries) -> tuple[list[float], list[int]] | None:
    parsed: list[tuple[datetime, int]] = []
    for timestamp_raw, value_raw in data:
        if not isinstance(timestamp_raw, str):
            continue
        try:
            timestamp = datetime.fromisoformat(timestamp_raw.replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            else:
                timestamp = timestamp.astimezone(timezone.utc)
            value = int(value_raw)
        except TypeError, ValueError:
            continue
        parsed.append((timestamp, value))

    if not parsed:
        return None

    parsed.sort(key=lambda item: item[0])
    t0 = parsed[0][0]
    elapsed_seconds = [(timestamp - t0).total_seconds() for timestamp, _ in parsed]
    values = [value for _, value in parsed]
    return elapsed_seconds, values
