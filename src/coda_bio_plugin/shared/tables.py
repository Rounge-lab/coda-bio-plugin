"""Unrestricted tables using the installed workflow-coda core helpers.

This private integration must be tested when workflow-coda is upgraded.
"""

from workflow_coda.context import RenderContext
from workflow_coda.core.table import (
    _assemble_markup,
    _controls_bar,
    _RenderedTable,
    _sort_icons_html,
    _TableSpec,
)


def table_html(
    context: RenderContext,
    headers: tuple[str, ...],
    rows: tuple[tuple[str, ...], ...],
    *,
    artifact_type: str,
) -> str:
    """Preserve all supplied cells without width or viewport restrictions."""
    if not headers:
        return ""

    rendered = _RenderedTable(labels=headers, rows=rows)
    spec = _TableSpec(
        artifact_type=artifact_type,
        sep="\t",
        header=True,
        columns=None,
        caption=None,
        column_widths=None,
        max_visible_rows=None,
        copy_rows="all",
    )
    return _assemble_markup(
        rendered,
        spec=spec,
        sort_icons=_sort_icons_html(context),
        controls_bar=_controls_bar(context),
        column_group="",
    )
