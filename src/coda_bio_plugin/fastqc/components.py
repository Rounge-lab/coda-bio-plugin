"""FastQC overview, tables, and chart component declarations."""

import html
from collections import Counter
from dataclasses import replace
from importlib import resources
from typing import Final

from workflow_coda.components import (
    ComponentChrome,
    ComponentParameters,
    PlacementInfo,
    RenderedComponent,
    ReportComponent,
)
from workflow_coda.context import RenderContext
from workflow_coda.errors import ArtifactUnavailableError, PluginAssetError

from .figures import (
    FigureBuilder,
    build_adapter_content,
    build_per_base_n_content,
    build_per_base_sequence_content,
    build_per_base_sequence_quality,
    build_per_sequence_gc_content,
    build_per_sequence_quality_scores,
    build_sequence_duplication_levels,
    build_sequence_length_distribution,
)
from .parser import MODULE_NAMES, FastqcModule, FastqcReport
from .rendering import (
    STATUS_PRESENTATION,
    RenderSpec,
    caption_html,
    disclosure_html,
    missing_module_message,
    module_metadata_html,
    module_table_html,
    parse_parameters,
    read_report,
    status_badge,
)


def _load_css() -> str:
    try:
        return (
            resources.files("coda_bio_plugin")
            .joinpath("assets", "fastqc.css")
            .read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError) as exc:
        raise PluginAssetError(
            "coda-bio-plugin asset 'assets/fastqc.css' is missing or unreadable "
            "— reinstall coda-bio-plugin"
        ) from exc


FASTQC_CSS: Final[str] = _load_css()


def _read(
    context: RenderContext,
    component_id: str,
    parameters: ComponentParameters,
    *,
    supports_table: bool,
) -> tuple[FastqcReport | None, str | None, RenderSpec]:
    """Validate first, then read; convert only missing artifacts."""
    spec = parse_parameters(component_id, parameters, supports_table=supports_table)
    try:
        report = read_report(context, component_id, spec)
    except ArtifactUnavailableError as exc:
        return None, str(exc), spec
    return report, None, spec


def _overview_item(context: RenderContext, name: str, status: str | None) -> str:
    if status is None:
        return (
            '<li class="coda-bio-fastqc__overview-item '
            'coda-bio-fastqc__overview-item--unavailable">'
            f"<span>{html.escape(name)}</span>"
            "<span>Unavailable</span></li>"
        )
    icon_name, token, label = STATUS_PRESENTATION[status]
    icon = context.icons.load(icon_name).markup
    color = html.escape(context.theme.colors[token], quote=True)
    return (
        '<li class="coda-bio-fastqc__overview-item" '
        f'style="border-left-color: {color};">'
        f"<span>{html.escape(name)}</span>"
        '<span class="coda-bio-fastqc__overview-status">'
        f'<span class="coda-bio-fastqc__icon" style="color: {color};">'
        f"{icon}</span> {html.escape(label)}</span></li>"
    )


def _additional_modules(modules: tuple[FastqcModule, ...]) -> str:
    additional = [module for module in modules if module.name not in MODULE_NAMES]
    if not additional:
        return ""
    items = "".join(
        f"<li>{html.escape(module.name)}: "
        f"{html.escape(STATUS_PRESENTATION[module.status][2])}</li>"
        for module in additional
    )
    return (
        '<details class="coda-bio-fastqc__disclosure">'
        f"<summary>Additional modules</summary><ul>{items}</ul></details>"
    )


def render_overview(
    context: RenderContext, _info: PlacementInfo, parameters: ComponentParameters
) -> RenderedComponent:
    """Summarize the ten standard modules without inventing missing statuses."""
    component_id = "bio.fastqc_overview"
    report, unavailable, spec = _read(
        context, component_id, parameters, supports_table=False
    )
    if unavailable is not None:
        return RenderedComponent.unavailable(unavailable)
    assert report is not None
    modules = {module.name: module for module in report.modules}
    counts: Counter[str] = Counter(
        modules[name].status for name in MODULE_NAMES if name in modules
    )
    missing = sum(name not in modules for name in MODULE_NAMES)
    items = "".join(
        _overview_item(context, name, modules[name].status if name in modules else None)
        for name in MODULE_NAMES
    )
    summary = (
        f"Pass: {counts['pass']}; Warn: {counts['warn']}; "
        f"Fail: {counts['fail']}; Unavailable: {missing}"
    )
    return RenderedComponent.from_html(
        '<div class="coda-bio-fastqc">'
        f"<p>FastQC version: {html.escape(report.version)}</p>"
        f'<ul class="coda-bio-fastqc__overview">{items}</ul>'
        f'<p class="coda-bio-fastqc__counts">{summary}</p>'
        f"{_additional_modules(report.modules)}"
        f"{caption_html(spec.caption)}</div>"
    )


def _module(
    context: RenderContext,
    component_id: str,
    parameters: ComponentParameters,
    module_name: str,
    *,
    supports_table: bool,
) -> tuple[FastqcModule | None, str | None, RenderSpec]:
    report, unavailable, spec = _read(
        context, component_id, parameters, supports_table=supports_table
    )
    if unavailable is not None:
        return None, unavailable, spec
    assert report is not None
    module = report.find_module(module_name)
    if module is None:
        return None, missing_module_message(component_id, spec, module_name), spec
    return module, None, spec


def _render_table(
    context: RenderContext,
    parameters: ComponentParameters,
    component_id: str,
    module_name: str,
    *,
    supports_table: bool,
) -> RenderedComponent:
    module, unavailable, spec = _module(
        context,
        component_id,
        parameters,
        module_name,
        supports_table=supports_table,
    )
    if unavailable is not None:
        return RenderedComponent.unavailable(unavailable)
    assert module is not None
    include_table = True if module_name == "Basic Statistics" else spec.include_table
    return RenderedComponent.from_html(
        '<div class="coda-bio-fastqc">'
        f"{status_badge(context, module.status)}"
        f"{module_table_html(module, include_table)}"
        f"{caption_html(spec.caption)}</div>"
    )


def render_basic_statistics(
    context: RenderContext, _info: PlacementInfo, parameters: ComponentParameters
) -> RenderedComponent:
    return _render_table(
        context,
        parameters,
        "bio.fastqc_basic_statistics",
        "Basic Statistics",
        supports_table=False,
    )


def render_overrepresented_sequences(
    context: RenderContext, _info: PlacementInfo, parameters: ComponentParameters
) -> RenderedComponent:
    return _render_table(
        context,
        parameters,
        "bio.fastqc_overrepresented_sequences",
        "Overrepresented sequences",
        supports_table=True,
    )


def _render_chart(
    context: RenderContext,
    parameters: ComponentParameters,
    component_id: str,
    module_name: str,
    builder: FigureBuilder,
    explanation: str = "",
) -> RenderedComponent:
    module, unavailable, spec = _module(
        context,
        component_id,
        parameters,
        module_name,
        supports_table=True,
    )
    if unavailable is not None:
        return RenderedComponent.unavailable(unavailable)
    assert module is not None
    badge = status_badge(context, module.status)
    if not module.rows:
        return RenderedComponent.from_html(
            '<div class="coda-bio-fastqc">'
            f"{badge}{module_table_html(module, spec.include_table)}"
            f"{caption_html(spec.caption)}</div>"
        )

    figure, description = builder(context.theme, module)
    result = RenderedComponent.from_figure(figure, description=description)
    assert result.html is not None
    metadata = module_metadata_html(module)
    disclosure = disclosure_html(module) if spec.include_table and module.header else ""
    return replace(
        result,
        html=(
            '<div class="coda-bio-fastqc">'
            f"{badge}{metadata}{result.html}{explanation}{disclosure}"
            f"{caption_html(spec.caption)}</div>"
        ),
    )


def render_per_base_sequence_quality(
    context: RenderContext, _info: PlacementInfo, parameters: ComponentParameters
) -> RenderedComponent:
    return _render_chart(
        context,
        parameters,
        "bio.fastqc_per_base_sequence_quality",
        "Per base sequence quality",
        build_per_base_sequence_quality,
        '<p class="coda-bio-fastqc__explanation">'
        "Whiskers represent the 10th and 90th percentiles. "
        "Background bands are presentation guides and do not replace "
        "FastQC’s reported status.</p>",
    )


def render_per_sequence_quality_scores(
    context: RenderContext, _info: PlacementInfo, parameters: ComponentParameters
) -> RenderedComponent:
    return _render_chart(
        context,
        parameters,
        "bio.fastqc_per_sequence_quality_scores",
        "Per sequence quality scores",
        build_per_sequence_quality_scores,
    )


def render_per_base_sequence_content(
    context: RenderContext, _info: PlacementInfo, parameters: ComponentParameters
) -> RenderedComponent:
    return _render_chart(
        context,
        parameters,
        "bio.fastqc_per_base_sequence_content",
        "Per base sequence content",
        build_per_base_sequence_content,
    )


def render_per_sequence_gc_content(
    context: RenderContext, _info: PlacementInfo, parameters: ComponentParameters
) -> RenderedComponent:
    return _render_chart(
        context,
        parameters,
        "bio.fastqc_per_sequence_gc_content",
        "Per sequence GC content",
        build_per_sequence_gc_content,
    )


def render_per_base_n_content(
    context: RenderContext, _info: PlacementInfo, parameters: ComponentParameters
) -> RenderedComponent:
    return _render_chart(
        context,
        parameters,
        "bio.fastqc_per_base_n_content",
        "Per base N content",
        build_per_base_n_content,
    )


def render_sequence_length_distribution(
    context: RenderContext, _info: PlacementInfo, parameters: ComponentParameters
) -> RenderedComponent:
    return _render_chart(
        context,
        parameters,
        "bio.fastqc_sequence_length_distribution",
        "Sequence Length Distribution",
        build_sequence_length_distribution,
    )


def render_sequence_duplication_levels(
    context: RenderContext, _info: PlacementInfo, parameters: ComponentParameters
) -> RenderedComponent:
    return _render_chart(
        context,
        parameters,
        "bio.fastqc_sequence_duplication_levels",
        "Sequence Duplication Levels",
        build_sequence_duplication_levels,
    )


def render_adapter_content(
    context: RenderContext, _info: PlacementInfo, parameters: ComponentParameters
) -> RenderedComponent:
    return _render_chart(
        context,
        parameters,
        "bio.fastqc_adapter_content",
        "Adapter Content",
        build_adapter_content,
    )


FASTQC_COMPONENTS: Final[tuple[ReportComponent, ...]] = (
    ReportComponent(
        id="bio.fastqc_overview",
        title="FastQC overview",
        description="Reported FastQC module statuses.",
        render=render_overview,
        chrome=ComponentChrome.CARD,
        css=FASTQC_CSS,
        js=None,
    ),
    ReportComponent(
        id="bio.fastqc_basic_statistics",
        title="Basic Statistics",
        description="Reported FastQC basic statistics.",
        render=render_basic_statistics,
        chrome=ComponentChrome.CARD,
        css=FASTQC_CSS,
        js=None,
    ),
    ReportComponent(
        id="bio.fastqc_per_base_sequence_quality",
        title="Per base sequence quality",
        description="Reported per-base quality distributions.",
        render=render_per_base_sequence_quality,
        chrome=ComponentChrome.CARD,
        css=FASTQC_CSS,
        js=None,
    ),
    ReportComponent(
        id="bio.fastqc_per_sequence_quality_scores",
        title="Per sequence quality scores",
        description="Reported sequence quality counts.",
        render=render_per_sequence_quality_scores,
        chrome=ComponentChrome.CARD,
        css=FASTQC_CSS,
        js=None,
    ),
    ReportComponent(
        id="bio.fastqc_per_base_sequence_content",
        title="Per base sequence content",
        description="Reported per-base nucleotide percentages.",
        render=render_per_base_sequence_content,
        chrome=ComponentChrome.CARD,
        css=FASTQC_CSS,
        js=None,
    ),
    ReportComponent(
        id="bio.fastqc_per_sequence_gc_content",
        title="Per sequence GC content",
        description="Reported sequence GC counts.",
        render=render_per_sequence_gc_content,
        chrome=ComponentChrome.CARD,
        css=FASTQC_CSS,
        js=None,
    ),
    ReportComponent(
        id="bio.fastqc_per_base_n_content",
        title="Per base N content",
        description="Reported per-base N percentages.",
        render=render_per_base_n_content,
        chrome=ComponentChrome.CARD,
        css=FASTQC_CSS,
        js=None,
    ),
    ReportComponent(
        id="bio.fastqc_sequence_length_distribution",
        title="Sequence Length Distribution",
        description="Reported sequence length counts.",
        render=render_sequence_length_distribution,
        chrome=ComponentChrome.CARD,
        css=FASTQC_CSS,
        js=None,
    ),
    ReportComponent(
        id="bio.fastqc_sequence_duplication_levels",
        title="Sequence Duplication Levels",
        description="Reported sequence duplication percentages.",
        render=render_sequence_duplication_levels,
        chrome=ComponentChrome.CARD,
        css=FASTQC_CSS,
        js=None,
    ),
    ReportComponent(
        id="bio.fastqc_overrepresented_sequences",
        title="Overrepresented sequences",
        description="Reported overrepresented sequences.",
        render=render_overrepresented_sequences,
        chrome=ComponentChrome.CARD,
        css=FASTQC_CSS,
        js=None,
    ),
    ReportComponent(
        id="bio.fastqc_adapter_content",
        title="Adapter Content",
        description="Reported adapter percentages by position.",
        render=render_adapter_content,
        chrome=ComponentChrome.CARD,
        css=FASTQC_CSS,
        js=None,
    ),
)
