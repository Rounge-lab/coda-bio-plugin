"""Figures built from validated fastp aggregates.

Counts and quality scores are retained as supplied. Content fractions are
converted to percentages for display. No QC statuses or thresholds are
invented.

Components handle empty results before invoking these builders.
"""

from collections.abc import Mapping
from typing import Final

from workflow_coda.theme import Theme, ThemePair

from ..shared.figures import (
    FigureResult,
    TraceUpdates,
    bind_theme,
    plotly,
    style_figure,
)
from .parser import FastpFilteringResult, FastpInsertSize, FastpRead

QUALITY_NAMES: Final[tuple[str, ...]] = ("A", "T", "C", "G", "mean")
CONTENT_NAMES: Final[tuple[str, ...]] = ("A", "T", "C", "G", "N", "GC")


def filtering_counts(
    result: FastpFilteringResult,
) -> tuple[tuple[str, int], ...]:
    """Return supplied filtering outcomes, omitting absent optional counts."""
    counts: tuple[tuple[str, int], ...] = (
        ("Passed filter", result.passed_filter_reads),
        ("Low quality", result.low_quality_reads),
        ("Too many Ns", result.too_many_n_reads),
        ("Too short", result.too_short_reads),
    )
    if result.too_long_reads is not None:
        counts += (("Too long", result.too_long_reads),)
    return counts


def _bar_updates(theme: Theme) -> TraceUpdates:
    return ({"marker.color": theme.series[0]},)


def _line_updates(theme: Theme, names: tuple[str, ...]) -> TraceUpdates:
    return tuple(
        {
            "line.color": theme.series[index % len(theme.series)],
            "marker.color": theme.series[index % len(theme.series)],
        }
        for index, _ in enumerate(names)
    )


def build_filtering_result(
    pair: ThemePair, result: FastpFilteringResult
) -> FigureResult:
    """Display counts without deriving percentages or cross-section totals."""
    go = plotly(subject="fastp")
    counts = filtering_counts(result)
    labels = [name for name, _ in counts]
    values = [count for _, count in counts]
    figure = go.Figure(
        go.Bar(
            x=labels,
            y=values,
            marker={"color": pair.light.series[0], "line_width": 0},
            hovertemplate="%{x}<br>Reads: %{y}<extra></extra>",
        )
    )
    style_figure(figure, pair.light, "Filtering outcome", "Reads")
    figure.update_xaxes(
        type="category",
        categoryorder="array",
        categoryarray=labels,
    )
    figure.update_yaxes(rangemode="tozero")
    description = (
        f"Bar chart of {len(counts)} supplied fastp filtering outcomes; "
        f"sum of reported counts: {sum(values)}"
    )
    return figure, description, bind_theme(pair, _bar_updates)


def build_insert_size(pair: ThemePair, result: FastpInsertSize) -> FigureResult:
    """Use histogram indices as insert sizes, preserving zero-count bins."""
    go = plotly(subject="fastp")
    figure = go.Figure(
        go.Bar(
            x=list(range(len(result.histogram))),
            y=list(result.histogram),
            marker={"color": pair.light.series[0], "line_width": 0},
            hovertemplate="Insert size: %{x}<br>Count: %{y}<extra></extra>",
        )
    )
    style_figure(figure, pair.light, "Insert size (bp)", "Count")
    figure.update_layout(bargap=0, bargroupgap=0)
    figure.update_xaxes(type="linear")
    figure.update_yaxes(rangemode="tozero")
    description = (
        f"Histogram of insert size, {len(result.histogram)} supplied bins; "
        f"reported peak: {result.peak} bp; "
        f"reported unknown count: {result.unknown}. "
        "The unknown count is not plotted as an insert-size bin."
    )
    return figure, description, bind_theme(pair, _bar_updates)


def _curves(
    pair: ThemePair,
    read: FastpRead,
    curves: Mapping[str, tuple[float, ...]],
    names: tuple[str, ...],
    *,
    percent: bool,
) -> FigureResult:
    go = plotly(subject="fastp")
    cycles = list(range(1, read.total_cycles + 1))
    figure = go.Figure()
    for index, name in enumerate(names):
        color = pair.light.series[index % len(pair.light.series)]
        values = (
            [value * 100 for value in curves[name]] if percent else list(curves[name])
        )
        figure.add_trace(
            go.Scatter(
                x=cycles,
                y=values,
                name="Mean" if name == "mean" else name,
                mode="lines",
                line={"color": color},
                marker={"color": color},
                hovertemplate=(
                    "Cycle: %{x}<br>Percent: %{y}<extra>%{fullData.name}</extra>"
                    if percent
                    else "Cycle: %{x}<br>Quality score: %{y}"
                    "<extra>%{fullData.name}</extra>"
                ),
            )
        )

    style_figure(
        figure,
        pair.light,
        "Cycle",
        "Percent" if percent else "Quality score",
    )
    figure.update_xaxes(type="linear", dtick=1 if read.total_cycles <= 20 else None)
    if percent:
        figure.update_yaxes(range=[0, 100])
    else:
        figure.update_yaxes(rangemode="tozero")

    subject = "base content" if percent else "quality scores"
    description = (
        f"Line chart of reported per-cycle {subject}; "
        f"{read.total_cycles} supplied cycles; "
        f"{len(names)} series: {', '.join(names)}"
    )
    if percent:
        description += ". Supplied fractions are displayed as percentages."
    return (
        figure,
        description,
        bind_theme(pair, lambda theme: _line_updates(theme, names)),
    )


def build_quality_curves(pair: ThemePair, read: FastpRead) -> FigureResult:
    """Display supplied scores without an arbitrary quality ceiling."""
    return _curves(
        pair,
        read,
        read.quality_curves,
        QUALITY_NAMES,
        percent=False,
    )


def build_content_curves(pair: ThemePair, read: FastpRead) -> FigureResult:
    """Display all supported content series, including overlapping GC."""
    return _curves(
        pair,
        read,
        read.content_curves,
        CONTENT_NAMES,
        percent=True,
    )
