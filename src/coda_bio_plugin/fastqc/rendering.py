"""Shared FastQC parameter, artifact, status, and HTML rendering support."""

import html
from dataclasses import dataclass
from typing import Final, cast

from workflow_coda.components import ComponentParameters, reject_unknown_parameters
from workflow_coda.context import RenderContext
from workflow_coda.core.table import (
    _assemble_markup,
    _controls_bar,
    _RenderedTable,
    _sort_icons_html,
)
from workflow_coda.errors import ArtifactReadError
from workflow_coda.text import has_visible_text

from .parser import FastqcModule, FastqcParseError, FastqcReport, parse_fastqc

_PARAMETERS: Final[frozenset[str]] = frozenset({"artifact", "caption"})
_TABLE_PARAMETERS: Final[frozenset[str]] = _PARAMETERS | {"include_table"}

# Icon, theme token, visible label.
STATUS_PRESENTATION: Final[dict[str, tuple[str, str, str]]] = {
    "pass": ("core-check", "success", "Pass"),
    "warn": ("core-info", "warning", "Warn"),
    "fail": ("core-warning", "danger", "Fail"),
}


@dataclass(frozen=True, slots=True)
class RenderSpec:
    """The parameters accepted by a FastQC component."""

    artifact_type: str
    caption: str | None
    include_table: bool


def parse_parameters(
    component_id: str,
    parameters: ComponentParameters,
    *,
    supports_table: bool,
) -> RenderSpec:
    """Validate component parameters before accessing artifact data."""
    accepted_parameters = _TABLE_PARAMETERS if supports_table else _PARAMETERS
    reject_unknown_parameters(component_id, parameters, accepted_parameters)

    def text_parameter(name: str, *, required: bool) -> str | None:
        if name not in parameters:
            if required:
                raise ValueError(
                    f"{component_id}: parameter {name!r} is required and must "
                    "be a string containing visible text; got missing"
                )
            return None
        value = parameters[name]
        if not isinstance(value, str) or not has_visible_text(value):
            raise ValueError(
                f"{component_id}: parameter {name!r} must be a string "
                f"containing visible text, got {value!r}"
            )
        return value

    artifact_type = text_parameter("artifact", required=True)
    assert artifact_type is not None

    include_table = False
    if supports_table and "include_table" in parameters:
        value = parameters["include_table"]
        if not isinstance(value, bool):
            raise ValueError(
                f"{component_id}: parameter 'include_table' must be a boolean, "
                f"got {value!r}"
            )
        include_table = value

    return RenderSpec(
        artifact_type=artifact_type,
        caption=text_parameter("caption", required=False),
        include_table=include_table,
    )


def read_report(
    context: RenderContext, component_id: str, spec: RenderSpec
) -> FastqcReport:
    """Read and parse a FastQC artifact through the framework store."""
    artifact = context.store.require(spec.artifact_type)
    declaration = artifact.declaration
    if declaration.format != "bio.fastqc":
        raise ValueError(
            f"{component_id}: artifact {spec.artifact_type!r} has format "
            f"{declaration.format!r}; expected 'bio.fastqc'"
        )
    text = artifact.read_text()
    try:
        return parse_fastqc(text)
    except FastqcParseError as exc:
        raise ArtifactReadError(
            f"{component_id}: artifact {declaration.id!r} "
            f"({spec.artifact_type!r}) is not valid bio.fastqc data: {exc}"
        ) from exc


def missing_module_message(component_id: str, spec: RenderSpec, name: str) -> str:
    """Explain why an individual component cannot render."""
    return (
        f"{component_id}: artifact {spec.artifact_type!r} carries no module "
        f"{name!r} — this component requires that module"
    )


def status_badge(context: RenderContext, status: str) -> str:
    """Render the reported status as visible text with a themed border."""
    _, token, label = STATUS_PRESENTATION[status]
    color = html.escape(context.theme.colors[token], quote=True)
    return (
        '<span class="coda-bio-fastqc__status" '
        f'style="border-left-color: {color};">{html.escape(label)}</span>'
    )


def caption_html(caption: str | None) -> str:
    """Render optional author text."""
    if caption is None:
        return ""
    return f'<p class="coda-bio-fastqc__caption">{html.escape(caption)}</p>'


def table_html(
    context: RenderContext,
    headers: tuple[str, ...],
    rows: tuple[tuple[str, ...], ...],
) -> str:
    """Assemble a complete table using workflow-coda's core table helpers.

    This deliberately uses private core helpers so FastQC tables share the
    installed core table's controls, sort affordances, escaping, and markup.
    That is a version-coupled integration: test it whenever workflow-coda is
    upgraded.
    """
    if not headers:
        return ""
    rendered = _RenderedTable(labels=headers, rows=rows)
    return cast(
        str,
        _assemble_markup(
            rendered,
            caption=None,
            sort_icons=_sort_icons_html(context),
            controls_bar=_controls_bar(context),
        ),
    )


def module_metadata_html(module: FastqcModule) -> str:
    """Render module metadata independently of its optional table."""
    if not module.metadata:
        return ""

    entries = []
    for key, value in module.metadata:
        if key == "Total Deduplicated Percentage":
            value = f"{float(value):.2f}"
        entries.append(f"<dt>{html.escape(key)}</dt><dd>{html.escape(value)}</dd>")
    return f'<dl class="coda-bio-fastqc__metadata">{"".join(entries)}</dl>'


def module_table_html(
    context: RenderContext, module: FastqcModule, include_table: bool
) -> str:
    """Render metadata, an optional complete table, and any empty-result notice."""
    table = table_html(context, module.header, module.rows) if include_table else ""
    empty = (
        '<p class="coda-bio-fastqc__empty">This module contains no data rows.</p>'
        if not module.rows
        else ""
    )
    return module_metadata_html(module) + table + empty


def disclosure_html(context: RenderContext, module: FastqcModule) -> str:
    """Wrap the complete module table in a native disclosure."""
    return (
        '<details class="coda-bio-fastqc__disclosure">'
        "<summary>Data table</summary>"
        f"{table_html(context, module.header, module.rows)}"
        "</details>"
    )
