"""Shared FastQC parameter, artifact, status, and HTML rendering support."""

import html
from typing import Final

from workflow_coda.context import RenderContext
from workflow_coda.errors import ArtifactReadError
from workflow_coda.theme import color_css

from ..shared.rendering import (
    RenderSpec as RenderSpec,
)
from ..shared.rendering import (
    caption_html as shared_caption_html,
)
from ..shared.rendering import (
    disclosure_html as shared_disclosure_html,
)
from ..shared.rendering import (
    disclosure_summary_html as shared_disclosure_summary_html,
)
from ..shared.rendering import (
    parse_parameters as parse_parameters,
)
from ..shared.tables import table_html as shared_table_html
from .parser import FastqcModule, FastqcParseError, FastqcReport, parse_fastqc

# Icon, theme token, visible label.
STATUS_PRESENTATION: Final[dict[str, tuple[str, str, str]]] = {
    "pass": ("core-check", "success", "Pass"),
    "warn": ("core-info", "warning", "Warn"),
    "fail": ("core-warning", "danger", "Fail"),
}


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
    color = html.escape(
        color_css(context.theme, "bio.fastqc", token),
        quote=True,
    )
    return (
        '<span class="coda-bio-fastqc__status" '
        f'style="border-left-color: {color};">{html.escape(label)}</span>'
    )


def caption_html(caption: str | None) -> str:
    return shared_caption_html(caption, namespace="coda-bio-fastqc")


def table_html(
    context: RenderContext,
    headers: tuple[str, ...],
    rows: tuple[tuple[str, ...], ...],
) -> str:
    return shared_table_html(
        context,
        headers,
        rows,
        artifact_type="bio.fastqc",
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


def disclosure_summary_html(context: RenderContext, title: str) -> str:
    return shared_disclosure_summary_html(
        context,
        title,
        namespace="coda-bio-fastqc",
    )


def disclosure_html(context: RenderContext, module: FastqcModule) -> str:
    return shared_disclosure_html(
        context,
        "Data table",
        table_html(context, module.header, module.rows),
        namespace="coda-bio-fastqc",
    )
