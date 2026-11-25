"""Lazy Plotly loading and presentation-only figure theme infrastructure."""

import html
from collections.abc import Callable
from typing import Any, Protocol

from workflow_coda.artifact_store import JsonValue
from workflow_coda.components import SupportsToHtml
from workflow_coda.errors import RenderError
from workflow_coda.theme import FigureStyle, FigureTheme, Theme, ThemePair

type AxisRange = tuple[str | float, str | float]
type FigureResult = tuple[SupportsPlotlyFigure, str, FigureTheme]
type LayoutStyler = Callable[[Theme], dict[str, JsonValue]]
type TraceStyler = Callable[[Theme], TraceUpdates]
type TraceUpdates = tuple[dict[str, JsonValue], ...]


class SupportsPlotlyFigure(SupportsToHtml, Protocol):
    """A renderable Plotly-compatible figure."""

    def to_plotly_json(self) -> dict[str, Any]: ...


def style_figure(figure: Any, theme: Theme, x_title: str, y_title: str) -> None:
    """Initialize presentation and axis policy for one figure."""
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


def layout_updates(theme: Theme) -> dict[str, JsonValue]:
    """Presentation updates only; preserve axis policy and reader state."""
    border = theme.colors["border"]
    return {
        "paper_bgcolor": "rgba(0, 0, 0, 0)",
        "plot_bgcolor": "rgba(0, 0, 0, 0)",
        "font.family": theme.font_body,
        "font.color": theme.text_on(theme.colors["surface"]),
        "xaxis.gridcolor": border,
        "xaxis.linecolor": border,
        "xaxis.zerolinecolor": border,
        "yaxis.gridcolor": border,
        "yaxis.linecolor": border,
        "yaxis.zerolinecolor": border,
    }


def plotly(*, subject: str) -> Any:
    """Import Plotly only when a non-empty chart needs it."""
    try:
        import plotly.graph_objects as go
    except ImportError as exc:
        raise RenderError(
            f"{subject} charts require plotly, which is not installed or cannot "
            "be imported — install plotly and build again"
        ) from exc
    return go


def bind_theme(
    pair: ThemePair,
    trace_style: TraceStyler,
    *,
    extra_layout: LayoutStyler | None = None,
) -> FigureTheme:
    """Resolve presentation updates independently for both theme modes."""

    def style(theme: Theme) -> FigureStyle:
        layout = layout_updates(theme)
        if extra_layout is not None:
            layout.update(extra_layout(theme))
        return FigureStyle(layout=layout, traces=trace_style(theme))

    return FigureTheme(light=style(pair.light), dark=style(pair.dark))
