"""Fastp summary, tables, and chart component declarations."""

import html
from dataclasses import replace
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
from ..shared.figures import FigureResult
from .figures import (
    build_content_curves,
    build_filtering_result,
    build_insert_size,
    build_quality_curves,
)
from .parser import FastpReport
from .rendering import (
    RenderSpec,
    TableRows,
    adapter_counts_html,
    caption_html,
    curve_table,
    disclosure_html,
    empty_html,
    filtering_rows,
    insert_size_rows,
    missing_section_message,
    parse_parameters,
    read_report,
    selected_read,
    summary_rows,
    table_html,
)


def _read(
    context: RenderContext,
    component_id: str,
    parameters: ComponentParameters,
    *,
    supports_table: bool = False,
    requires_section: bool = False,
) -> tuple[FastpReport | None, str | None, RenderSpec]:
    """Validate all parameters first; convert only unavailable artifacts."""
    spec = parse_parameters(
        component_id,
        parameters,
        supports_table=supports_table,
        requires_section=requires_section,
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


def _chart_result(
    context: RenderContext,
    spec: RenderSpec,
    figure_result: FigureResult | None,
    headers: tuple[str, ...],
    rows: TableRows,
    *,
    prefix: str = "",
    explanation: str = "",
    empty_message: str = "",
) -> RenderedComponent:
    """Wrap figure HTML without discarding framework figure metadata."""
    table = disclosure_html(context, headers, rows) if spec.include_table else ""
    if figure_result is None:
        return _result(
            prefix + empty_html(empty_message) + explanation + table,
            spec,
        )

    figure, description, binding = figure_result
    result = RenderedComponent.from_figure(
        figure,
        description=description,
        theme=binding,
    )
    assert result.html is not None
    return replace(
        result,
        html=(
            '<div class="coda-bio">'
            f"{prefix}{result.html}{explanation}{table}"
            f"{caption_html(spec.caption)}</div>"
        ),
    )


def render_filtering_result(
    context: RenderContext,
    _info: PlacementInfo,
    parameters: ComponentParameters,
) -> RenderedComponent:
    component_id = "bio.fastp_filtering_result"
    report, unavailable, spec = _read(
        context,
        component_id,
        parameters,
        supports_table=True,
    )
    if unavailable is not None:
        return RenderedComponent.unavailable(unavailable)
    assert report is not None
    filtering = report.filtering_result
    if filtering is None:
        return RenderedComponent.unavailable(
            missing_section_message(component_id, spec, "filtering_result")
        )

    # Required filtering outcomes remain meaningful even when all are zero.
    return _chart_result(
        context,
        spec,
        build_filtering_result(context.theme, filtering),
        ("Filtering outcome", "Reads"),
        filtering_rows(filtering),
    )


def render_insert_size(
    context: RenderContext,
    _info: PlacementInfo,
    parameters: ComponentParameters,
) -> RenderedComponent:
    component_id = "bio.fastp_insert_size"
    report, unavailable, spec = _read(
        context,
        component_id,
        parameters,
        supports_table=True,
    )
    if unavailable is not None:
        return RenderedComponent.unavailable(unavailable)
    assert report is not None
    insert = report.insert_size
    if insert is None:
        return RenderedComponent.unavailable(
            missing_section_message(component_id, spec, "insert_size")
        )

    metadata = (
        '<dl class="coda-bio__metadata">'
        f"<dt>Reported peak (bp)</dt><dd>{insert.peak}</dd>"
        f"<dt>Reported unknown count</dt><dd>{insert.unknown}</dd>"
        "</dl>"
    )
    explanation = (
        '<p class="coda-bio__explanation">'
        "The unknown count is not plotted as an insert-size bin.</p>"
    )
    figure_result = (
        build_insert_size(context.theme, insert) if insert.histogram else None
    )
    return _chart_result(
        context,
        spec,
        figure_result,
        ("Insert size (bp)", "Count"),
        insert_size_rows(insert),
        prefix=metadata,
        explanation=explanation,
        empty_message="This section contains no insert-size histogram bins.",
    )


def _render_curves(
    context: RenderContext,
    parameters: ComponentParameters,
    *,
    content: bool,
) -> RenderedComponent:
    component_id = "bio.fastp_content_curves" if content else "bio.fastp_quality_curves"
    report, unavailable, spec = _read(
        context,
        component_id,
        parameters,
        supports_table=True,
        requires_section=True,
    )
    if unavailable is not None:
        return RenderedComponent.unavailable(unavailable)
    assert report is not None
    assert spec.section is not None
    read = selected_read(report, spec.section)
    if read is None:
        return RenderedComponent.unavailable(
            missing_section_message(component_id, spec, spec.section)
        )

    headers, rows = curve_table(read, content=content)
    figure_result: FigureResult | None = None
    if read.total_cycles:
        builder = build_content_curves if content else build_quality_curves
        figure_result = builder(context.theme, read)

    label = spec.section.replace("_", " ")
    explanation = ""
    if content:
        explanation = (
            '<p class="coda-bio__explanation">'
            "Supplied fractions are displayed as percentages. "
            "GC overlaps the C and G series; the lines are not stacked.</p>"
        )
    return _chart_result(
        context,
        spec,
        figure_result,
        headers,
        rows,
        prefix=f"<p>Read section: {html.escape(label)}</p>",
        explanation=explanation,
        empty_message="This read section contains no cycles.",
    )


def render_quality_curves(
    context: RenderContext,
    _info: PlacementInfo,
    parameters: ComponentParameters,
) -> RenderedComponent:
    return _render_curves(context, parameters, content=False)


def render_content_curves(
    context: RenderContext,
    _info: PlacementInfo,
    parameters: ComponentParameters,
) -> RenderedComponent:
    return _render_curves(context, parameters, content=True)


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
    ReportComponent(
        id="bio.fastp_filtering_result",
        title="Filtering result",
        description="Reported fastp read counts by filtering outcome.",
        render=render_filtering_result,
        chrome=ComponentChrome.CARD,
        css=BIO_TABLE_CSS,
        js=BIO_TABLE_JS,
    ),
    ReportComponent(
        id="bio.fastp_insert_size",
        title="Insert size",
        description="Reported fastp insert-size histogram and metadata.",
        render=render_insert_size,
        chrome=ComponentChrome.CARD,
        css=BIO_TABLE_CSS,
        js=BIO_TABLE_JS,
    ),
    ReportComponent(
        id="bio.fastp_quality_curves",
        title="Quality curves",
        description="Reported fastp quality scores by cycle.",
        render=render_quality_curves,
        chrome=ComponentChrome.CARD,
        css=BIO_TABLE_CSS,
        js=BIO_TABLE_JS,
    ),
    ReportComponent(
        id="bio.fastp_content_curves",
        title="Content curves",
        description="Reported fastp base content by cycle.",
        render=render_content_curves,
        chrome=ComponentChrome.CARD,
        css=BIO_TABLE_CSS,
        js=BIO_TABLE_JS,
    ),
)
