"""Plotly figure construction for parsed FastQC modules.

The figures use the aggregated values in the artifact as supplied. No
observations, theoretical distributions, or QC judgments are invented.
"""

import html
import math
from collections.abc import Callable
from typing import Any, Protocol

from workflow_coda.components import SupportsToHtml
from workflow_coda.errors import RenderError
from workflow_coda.theme import Theme

from .parser import FastqcModule
from .rendering import STATUS_PRESENTATION

type AxisRange = tuple[str | float, str | float]


class SupportsPlotlyFigure(SupportsToHtml, Protocol):
    """A renderable Plotly-compatible figure."""

    def to_plotly_json(self) -> dict[str, Any]: ...


def _plotly() -> Any:
    """Import Plotly only when a non-empty chart needs it."""
    try:
        import plotly.graph_objects as go
    except ImportError as exc:
        raise RenderError(
            "FastQC charts require plotly, which is not installed or cannot "
            "be imported — install plotly and build again"
        ) from exc
    return go


def _values(module: FastqcModule, name: str) -> list[str]:
    index = module.header.index(name)
    return [row[index] for row in module.rows]


def _numbers(module: FastqcModule, name: str) -> list[float]:
    return [float(value) for value in _values(module, name)]


def _labels(module: FastqcModule, name: str) -> list[str]:
    return [html.escape(value) for value in _values(module, name)]


def _status(module: FastqcModule) -> str:
    return STATUS_PRESENTATION[module.status][2]


def _status_color(theme: Theme, module: FastqcModule) -> str:
    return theme.colors[STATUS_PRESENTATION[module.status][1]]


def _style(figure: Any, theme: Theme, x_title: str, y_title: str) -> None:
    border = theme.colors["border"]
    axis = {
        "showgrid": False,
        "gridcolor": border,
        "linecolor": border,
        "zerolinecolor": border,
        "showline": True,
    }
    figure.update_layout(
        paper_bgcolor="rgba(0, 0, 0, 0)",
        plot_bgcolor="rgba(0, 0, 0, 0)",
        font={
            "family": theme.font_body,
            "color": theme.text_on(theme.colors["surface"]),
        },
        xaxis={**axis, "title": {"text": html.escape(x_title)}},
        yaxis={**axis, "title": {"text": html.escape(y_title)}},
    )


def _description(module: FastqcModule, kind: str, subject: str) -> str:
    return (
        f"{kind} of {subject}, {len(module.rows)} supplied bins; "
        f"reported FastQC status: {_status(module)}"
    )


def build_per_base_sequence_quality(
    theme: Theme, module: FastqcModule
) -> tuple[SupportsPlotlyFigure, str]:
    """Precomputed quality boxes and the reported mean line."""
    go = _plotly()
    bins = _labels(module, "Base")
    q1 = _numbers(module, "Lower Quartile")
    median = _numbers(module, "Median")
    q3 = _numbers(module, "Upper Quartile")
    lower = _numbers(module, "10th Percentile")
    upper = _numbers(module, "90th Percentile")
    mean = _numbers(module, "Mean")
    all_values = q1 + median + q3 + lower + upper + mean
    minimum = min(0.0, min(all_values))
    maximum = max(40.0, max(all_values))
    padding = max((maximum - minimum) * 0.05, 1.0)
    low = minimum - padding if minimum < 0 else minimum
    high = maximum + padding if maximum > 40 else maximum

    figure = go.Figure()
    figure.add_trace(
        go.Box(
            x=bins,
            q1=q1,
            median=median,
            q3=q3,
            lowerfence=lower,
            upperfence=upper,
            boxpoints=False,
            name="Quality percentiles",
            line={"color": theme.text_on(theme.colors["surface"]), "width": 1.2},
            fillcolor="rgba(0, 0, 0, 0)",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=bins,
            y=mean,
            mode="lines+markers",
            name="Mean",
            marker={"color": theme.text_on(theme.colors["surface"])},
            line={"color": theme.series[1]},
        )
    )
    for bottom, top, token in (
        (low, 20, "danger"),
        (20, 28, "warning"),
        (28, high, "success"),
    ):
        figure.add_hrect(
            y0=bottom,
            y1=top,
            fillcolor=theme.colors[token],
            opacity=0.15,
            line_width=0,
            layer="below",
        )
    _style(figure, theme, "Base", "Quality score")
    figure.update_xaxes(type="category", categoryorder="array", categoryarray=bins)
    figure.update_yaxes(range=[low, high])
    return figure, _description(
        module, "Box plot and mean line", "per-base sequence quality"
    )


def _bar(
    theme: Theme,
    module: FastqcModule,
    *,
    x_column: str,
    y_column: str,
    subject: str,
    categorical: bool,
    count: bool,
    x_range: AxisRange | None = None,
    y_range: AxisRange | None = None,
    x_fixed: bool = False,
    y_fixed: bool = False,
) -> tuple[SupportsPlotlyFigure, str]:
    go = _plotly()

    x: list[str] | list[float]
    x = _labels(module, x_column) if categorical else _numbers(module, x_column)
    y = _numbers(module, y_column)

    figure = go.Figure(
        go.Bar(
            x=x,
            y=y,
            marker={"color": _status_color(theme, module), "line_width": 0},
        )
    )

    figure.update_layout(bargap=0, bargroupgap=0)
    _style(figure, theme, x_column, "Percent" if not count else y_column)

    figure.update_xaxes(
        type="category" if categorical else "linear",
        categoryorder="array" if categorical else None,
        categoryarray=x if categorical else None,
        fixedrange=x_fixed,
    )
    figure.update_yaxes(fixedrange=y_fixed)

    if x_range is not None:
        figure.update_xaxes(range=list(x_range))

    if y_range is not None:
        figure.update_yaxes(range=list(y_range))

    description = _description(module, "Bar chart", subject)
    if count:
        description += f"; sum of reported counts: {math.fsum(y)}"

    return figure, description


def build_per_sequence_quality_scores(
    theme: Theme, module: FastqcModule
) -> tuple[SupportsPlotlyFigure, str]:
    return _bar(
        theme,
        module,
        x_column="Quality",
        y_column="Count",
        subject="per-sequence quality scores",
        categorical=False,
        count=True,
        x_range=(0, max(40, max(_numbers(module, "Quality")))),
        y_fixed=True,
    )


def build_per_sequence_gc_content(
    theme: Theme, module: FastqcModule
) -> tuple[SupportsPlotlyFigure, str]:
    return _bar(
        theme,
        module,
        x_column="GC Content",
        y_column="Count",
        subject="per-sequence GC content",
        categorical=False,
        count=True,
        y_fixed=True,
    )


def build_per_base_n_content(
    theme: Theme, module: FastqcModule
) -> tuple[SupportsPlotlyFigure, str]:
    return _bar(
        theme,
        module,
        x_column="Base",
        y_column="N-Count",
        subject="per-base N content",
        categorical=True,
        count=False,
    )


def build_sequence_length_distribution(
    theme: Theme, module: FastqcModule
) -> tuple[SupportsPlotlyFigure, str]:
    return _bar(
        theme,
        module,
        x_column="Length",
        y_column="Count",
        subject="sequence length distribution",
        categorical=True,
        count=True,
        y_fixed=True,
    )


def build_sequence_duplication_levels(
    theme: Theme, module: FastqcModule
) -> tuple[SupportsPlotlyFigure, str]:
    go = _plotly()
    labels = _labels(module, "Duplication Level")
    names = ("Percentage of deduplicated", "Percentage of total")
    figure = go.Figure()
    for index, name in enumerate(names):
        figure.add_trace(
            go.Bar(
                x=labels,
                y=_numbers(module, name),
                name=html.escape(name),
                marker={"color": theme.series[index], "line_width": 0},
            )
        )
    _style(figure, theme, "Duplication Level", "Percent")
    figure.update_layout(barmode="group", yaxis=dict(fixedrange=True))
    figure.update_xaxes(type="category", categoryorder="array", categoryarray=labels)
    description = _description(module, "Grouped bar chart", "sequence duplication")
    description += f"; {len(names)} series: {', '.join(names)}"
    return figure, description


def _heatmap(
    theme: Theme,
    module: FastqcModule,
    *,
    bin_column: str,
    names: tuple[str, ...],
    subject: str,
) -> tuple[SupportsPlotlyFigure, str]:
    go = _plotly()
    bins = _labels(module, bin_column)
    series = [html.escape(name) for name in names]
    figure = go.Figure(
        go.Heatmap(
            x=bins,
            y=series,
            z=[_numbers(module, name) for name in names],
            zmin=0,
            zmax=100,
            colorscale=[
                [0, theme.colors["surface"]],
                [1, _status_color(theme, module)],
            ],
            colorbar={"title": {"text": "Percent"}},
            hovertemplate="Series: %{y}<br>Bin: %{x}<br>Percent: %{z}<extra></extra>",
        )
    )
    _style(figure, theme, bin_column, "Series")
    figure.update_xaxes(type="category", categoryorder="array", categoryarray=bins)
    figure.update_yaxes(type="category", categoryorder="array", categoryarray=series)
    description = _description(module, "Percentage heatmap", subject)
    description += f"; {len(names)} series: {', '.join(names)}"
    return figure, description


def build_per_base_sequence_content(
    theme: Theme, module: FastqcModule
) -> tuple[SupportsPlotlyFigure, str]:
    return _heatmap(
        theme,
        module,
        bin_column="Base",
        names=("G", "A", "T", "C"),
        subject="per-base sequence content",
    )


def build_adapter_content(
    theme: Theme, module: FastqcModule
) -> tuple[SupportsPlotlyFigure, str]:
    return _heatmap(
        theme,
        module,
        bin_column="Position",
        names=module.header[1:],
        subject="adapter content",
    )


type FigureBuilder = Callable[[Theme, FastqcModule], tuple[SupportsPlotlyFigure, str]]
