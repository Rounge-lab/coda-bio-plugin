"""Fastp summary, duplication, and adapter-cutting components."""

import html
from typing import Final

from workflow_coda.components import (
    ComponentChrome,
    ComponentParameters,
    PlacementInfo,
    RenderedComponent,
    ReportComponent,
)
from workflow_coda.context import RenderContext
from workflow_coda.errors import ArtifactUnavailableError

from ..shared.component_assets import BIO_CSS, BIO_TABLE_CSS, BIO_TABLE_JS
from .parser import FastpReport
from .rendering import (
    RenderSpec,
    adapter_counts_html,
    caption_html,
    missing_section_message,
    parse_parameters,
    read_report,
    summary_rows,
    table_html,
)


def _read(
    context: RenderContext,
    component_id: str,
    parameters: ComponentParameters,
) -> tuple[FastpReport | None, str | None, RenderSpec]:
    """Validate first; convert only unavailable artifacts into outcomes."""
    spec = parse_parameters(
        component_id,
        parameters,
        supports_table=False,
    )
    try:
        report = read_report(context, component_id, spec)
    except ArtifactUnavailableError as exc:
        return None, str(exc), spec
    return report, None, spec


def _result(body: str, spec: RenderSpec) -> RenderedComponent:
    return RenderedComponent.from_html(
        f'<div class="coda-bio">{body}{caption_html(spec.caption)}</div>'
    )


def render_overview(
    context: RenderContext,
    _info: PlacementInfo,
    parameters: ComponentParameters,
) -> RenderedComponent:
    component_id = "bio.fastp_overview"
    report, unavailable, spec = _read(context, component_id, parameters)
    if unavailable is not None:
        return RenderedComponent.unavailable(unavailable)
    assert report is not None
    summary = report.summary
    if summary is None:
        return RenderedComponent.unavailable(
            missing_section_message(component_id, spec, "summary")
        )

    metadata = ""
    if summary.fastp_version is not None:
        metadata += f"<p>fastp version: {html.escape(summary.fastp_version)}</p>"
    if summary.sequencing is not None:
        metadata += f"<p>Sequencing: {html.escape(summary.sequencing)}</p>"

    return _result(
        metadata
        + table_html(
            context,
            ("Metric", "Before filtering", "After filtering"),
            summary_rows(summary),
        ),
        spec,
    )


def render_duplication(
    context: RenderContext,
    _info: PlacementInfo,
    parameters: ComponentParameters,
) -> RenderedComponent:
    component_id = "bio.fastp_duplication"
    report, unavailable, spec = _read(context, component_id, parameters)
    if unavailable is not None:
        return RenderedComponent.unavailable(unavailable)
    assert report is not None
    duplication = report.duplication
    if duplication is None:
        return RenderedComponent.unavailable(
            missing_section_message(component_id, spec, "duplication")
        )

    return _result(
        "<p>Reported duplication rate: "
        f"<strong>{duplication.rate * 100:.2f}%</strong></p>",
        spec,
    )


def _adapter_sequence(label: str, sequence: str | None) -> str:
    if sequence is None:
        value = "Not reported"
    elif not sequence:
        value = "Reported as empty"
    else:
        value = sequence
    return f"<dt>{html.escape(label)}</dt><dd>{html.escape(value)}</dd>"


def render_adapter_cutting(
    context: RenderContext,
    _info: PlacementInfo,
    parameters: ComponentParameters,
) -> RenderedComponent:
    component_id = "bio.fastp_adapter_cutting"
    report, unavailable, spec = _read(context, component_id, parameters)
    if unavailable is not None:
        return RenderedComponent.unavailable(unavailable)
    assert report is not None
    adapters = report.adapter_cutting
    if adapters is None:
        return RenderedComponent.unavailable(
            missing_section_message(component_id, spec, "adapter_cutting")
        )

    totals = table_html(
        context,
        ("Metric", "Count"),
        (
            ("Adapter-trimmed reads", str(adapters.adapter_trimmed_reads)),
            ("Adapter-trimmed bases", str(adapters.adapter_trimmed_bases)),
        ),
    )
    sequences = (
        '<dl class="coda-bio__metadata">'
        + _adapter_sequence("Read 1 adapter sequence", adapters.read1_adapter_sequence)
        + _adapter_sequence("Read 2 adapter sequence", adapters.read2_adapter_sequence)
        + "</dl>"
    )
    counts = adapter_counts_html(
        context,
        "Read 1 adapter counts",
        adapters.read1_adapter_counts,
    ) + adapter_counts_html(
        context,
        "Read 2 adapter counts",
        adapters.read2_adapter_counts,
    )
    return _result(totals + sequences + counts, spec)


FASTP_COMPONENTS: Final[tuple[ReportComponent, ...]] = (
    ReportComponent(
        id="bio.fastp_overview",
        title="fastp overview",
        description="Reported fastp metrics before and after filtering.",
        render=render_overview,
        chrome=ComponentChrome.CARD,
        css=BIO_TABLE_CSS,
        js=BIO_TABLE_JS,
    ),
    ReportComponent(
        id="bio.fastp_duplication",
        title="Duplication",
        description="Reported fastp duplication rate.",
        render=render_duplication,
        chrome=ComponentChrome.CARD,
        css=BIO_CSS,
        js=None,
    ),
    ReportComponent(
        id="bio.fastp_adapter_cutting",
        title="Adapter cutting",
        description="Reported adapter trimming totals, sequences, and counts.",
        render=render_adapter_cutting,
        chrome=ComponentChrome.CARD,
        css=BIO_TABLE_CSS,
        js=BIO_TABLE_JS,
    ),
)
