"""Shared FastQC parameter, artifact, status, and HTML rendering support."""

import html
from dataclasses import dataclass
from typing import Final

from workflow_coda.components import ComponentParameters, reject_unknown_parameters
from workflow_coda.context import RenderContext
from workflow_coda.errors import ArtifactReadError
from workflow_coda.text import has_visible_text

from .parser import FastqcModule, FastqcParseError, FastqcReport, parse_fastqc

_PARAMETERS: Final[frozenset[str]] = frozenset({"artifact", "caption"})

# Icon, theme token, visible label.
STATUS_PRESENTATION: Final[dict[str, tuple[str, str, str]]] = {
    "pass": ("core-check", "success", "Pass"),
    "warn": ("core-info", "warning", "Warn"),
    "fail": ("core-warning", "danger", "Fail"),
}


@dataclass(frozen=True, slots=True)
class RenderSpec:
    """The two parameters accepted by every FastQC component."""

    artifact_type: str
    caption: str | None


def parse_parameters(component_id: str, parameters: ComponentParameters) -> RenderSpec:
    """Validate the closed parameter vocabulary before accessing data."""
    reject_unknown_parameters(component_id, parameters, _PARAMETERS)

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
    return RenderSpec(
        artifact_type=artifact_type,
        caption=text_parameter("caption", required=False),
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
        f'style="border-color: {color};">{html.escape(label)}</span>'
    )


def caption_html(caption: str | None) -> str:
    """Render optional author text."""
    if caption is None:
        return ""
    return f'<p class="coda-bio-fastqc__caption">{html.escape(caption)}</p>'


def table_html(headers: tuple[str, ...], rows: tuple[tuple[str, ...], ...]) -> str:
    """Render every supplied header and cell in their original order."""
    if not headers:
        return ""
    head = "".join(f'<th scope="col">{html.escape(header)}</th>' for header in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    return (
        '<div class="coda-bio-fastqc__table-wrap">'
        '<table class="coda-bio-fastqc__table">'
        f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody>"
        "</table></div>"
    )


def module_table_html(module: FastqcModule) -> str:
    """Render module metadata, its complete table, and its empty-result notice."""
    metadata = ""
    if module.metadata:
        entries = "".join(
            f"<dt>{html.escape(key)}</dt><dd>{html.escape(value)}</dd>"
            for key, value in module.metadata
        )
        metadata = f'<dl class="coda-bio-fastqc__metadata">{entries}</dl>'
    empty = (
        '<p class="coda-bio-fastqc__empty">This module contains no data rows.</p>'
        if not module.rows
        else ""
    )
    return metadata + table_html(module.header, module.rows) + empty


def disclosure_html(module: FastqcModule) -> str:
    """Ship the complete module data in a native disclosure."""
    return (
        '<details class="coda-bio-fastqc__disclosure">'
        "<summary>Data table</summary>"
        f"{module_table_html(module)}"
        "</details>"
    )
