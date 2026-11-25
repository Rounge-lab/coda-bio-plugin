"""Fastp parameter validation, artifact loading, and table presentation.

Tool-independent markup and table infrastructure live in shared/.
Missing-artifact conversion belongs to the component layer.
"""

import html
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, cast

from workflow_coda.artifact_store import JsonValue
from workflow_coda.components import ComponentParameters
from workflow_coda.context import RenderContext
from workflow_coda.errors import ArtifactReadError

from ..shared.rendering import (
    caption_html as shared_caption_html,
)
from ..shared.rendering import (
    disclosure_html as shared_disclosure_html,
)
from ..shared.rendering import (
    parse_parameters as parse_common_parameters,
)
from ..shared.tables import table_html as shared_table_html
from .figures import CONTENT_NAMES, QUALITY_NAMES, filtering_counts
from .parser import (
    READ_SECTIONS,
    FastpFilteringResult,
    FastpInsertSize,
    FastpParseError,
    FastpRead,
    FastpReport,
    FastpSummary,
    parse_fastp,
)

NAMESPACE: Final[str] = "coda-bio"

type TableRows = tuple[tuple[str, ...], ...]


@dataclass(frozen=True, slots=True)
class RenderSpec:
    """Validated common parameters and optional read-section selection."""

    artifact_type: str
    caption: str | None
    include_table: bool
    section: str | None


def parse_parameters(
    component_id: str,
    parameters: ComponentParameters,
    *,
    supports_table: bool,
    requires_section: bool = False,
) -> RenderSpec:
    """Validate every parameter before accessing artifact data."""
    common = parse_common_parameters(
        component_id,
        parameters,
        supports_table=supports_table,
        extra_parameters=(frozenset({"section"}) if requires_section else frozenset()),
    )

    section: str | None = None
    if requires_section:
        value = parameters.get("section")
        if not isinstance(value, str) or value not in READ_SECTIONS:
            available = ", ".join(repr(name) for name in READ_SECTIONS)
            raise ValueError(
                f"{component_id}: parameter 'section' must name one of "
                f"{available}; got {value!r}"
            )
        section = value

    return RenderSpec(
        artifact_type=common.artifact_type,
        caption=common.caption,
        include_table=common.include_table,
        section=section,
    )


def _reject_constant(value: str) -> JsonValue:
    raise ValueError(f"non-standard numeric constant {value!r}")


def read_report(
    context: RenderContext,
    component_id: str,
    spec: RenderSpec,
) -> FastpReport:
    """Load checksum-verified UTF-8 JSON and validate supported fastp data."""
    artifact = context.store.require(spec.artifact_type)
    declaration = artifact.declaration
    if declaration.format != "bio.fastp":
        raise ValueError(
            f"{component_id}: artifact {spec.artifact_type!r} has format "
            f"{declaration.format!r}; expected 'bio.fastp'"
        )

    # Keep store IO and checksum failures outside the parsing exception
    # handler so their original framework error types remain intact.
    text = artifact.read_text()
    try:
        payload = cast(
            JsonValue,
            json.loads(text, parse_constant=_reject_constant),
        )
    except ValueError as exc:
        raise ArtifactReadError(
            f"{component_id}: artifact {declaration.id!r} "
            f"({spec.artifact_type!r}) is not valid JSON: {exc}"
        ) from exc

    try:
        return parse_fastp(payload)
    except FastpParseError as exc:
        raise ArtifactReadError(
            f"{component_id}: artifact {declaration.id!r} "
            f"({spec.artifact_type!r}) is not valid bio.fastp data: {exc}"
        ) from exc


def selected_read(report: FastpReport, section: str) -> FastpRead | None:
    """Resolve a validated read-section name without dynamic attribute access."""
    reads = {
        "read1_before_filtering": report.read1_before_filtering,
        "read2_before_filtering": report.read2_before_filtering,
        "read1_after_filtering": report.read1_after_filtering,
        "read2_after_filtering": report.read2_after_filtering,
    }
    return reads[section]


def missing_section_message(
    component_id: str,
    spec: RenderSpec,
    section: str,
) -> str:
    return (
        f"{component_id}: artifact {spec.artifact_type!r} carries no section "
        f"{section!r} — this component requires that section"
    )


def caption_html(caption: str | None) -> str:
    return shared_caption_html(caption, namespace=NAMESPACE)


def empty_html(message: str) -> str:
    return f'<p class="{NAMESPACE}__empty">{html.escape(message)}</p>'


def table_html(
    context: RenderContext,
    headers: tuple[str, ...],
    rows: TableRows,
) -> str:
    return shared_table_html(
        context,
        headers,
        rows,
        artifact_type="bio.fastp",
    )


def disclosure_html(
    context: RenderContext,
    headers: tuple[str, ...],
    rows: TableRows,
) -> str:
    return shared_disclosure_html(
        context,
        "Data table",
        table_html(context, headers, rows),
        namespace=NAMESPACE,
    )


def summary_rows(summary: FastpSummary) -> TableRows:
    """Present supplied before/after metrics without deriving QC judgments."""
    before = summary.before_filtering
    after = summary.after_filtering
    rows: TableRows = (
        ("Total reads", str(before.total_reads), str(after.total_reads)),
        ("Total bases", str(before.total_bases), str(after.total_bases)),
        ("Q20 bases", str(before.q20_bases), str(after.q20_bases)),
        ("Q30 bases", str(before.q30_bases), str(after.q30_bases)),
        (
            "Q20 rate (%)",
            str(before.q20_rate * 100),
            str(after.q20_rate * 100),
        ),
        (
            "Q30 rate (%)",
            str(before.q30_rate * 100),
            str(after.q30_rate * 100),
        ),
        (
            "Read 1 mean length (bp)",
            str(before.read1_mean_length),
            str(after.read1_mean_length),
        ),
        (
            "GC content (%)",
            str(before.gc_content * 100),
            str(after.gc_content * 100),
        ),
    )
    if before.read2_mean_length is not None or after.read2_mean_length is not None:
        rows += (
            (
                "Read 2 mean length (bp)",
                (
                    str(before.read2_mean_length)
                    if before.read2_mean_length is not None
                    else "Not reported"
                ),
                (
                    str(after.read2_mean_length)
                    if after.read2_mean_length is not None
                    else "Not reported"
                ),
            ),
        )
    return rows


def filtering_rows(result: FastpFilteringResult) -> TableRows:
    return tuple((name, str(count)) for name, count in filtering_counts(result))


def insert_size_rows(result: FastpInsertSize) -> TableRows:
    """Keep unknown counts separate from histogram data."""
    return tuple(
        (str(index), str(count)) for index, count in enumerate(result.histogram)
    )


def curve_table(
    read: FastpRead,
    *,
    content: bool,
) -> tuple[tuple[str, ...], TableRows]:
    """Use the same series order and units as the figure builders."""
    names = CONTENT_NAMES if content else QUALITY_NAMES
    curves = read.content_curves if content else read.quality_curves
    headers = ("Cycle",) + tuple(
        f"{name} (%)" if content else ("Mean" if name == "mean" else name)
        for name in names
    )
    rows = tuple(
        (str(index + 1),)
        + tuple(
            str(curves[name][index] * 100) if content else str(curves[name][index])
            for name in names
        )
        for index in range(read.total_cycles)
    )
    return headers, rows


def adapter_counts_html(
    context: RenderContext,
    label: str,
    counts: Mapping[str, int] | None,
) -> str:
    """Distinguish absent adapter counts from a supplied empty mapping."""
    heading = f"<h3>{html.escape(label)}</h3>"
    if counts is None:
        return heading + empty_html("Adapter counts were not reported.")
    if not counts:
        return heading + empty_html("No adapter-count entries were reported.")
    rows = tuple((sequence, str(count)) for sequence, count in counts.items())
    return heading + table_html(context, ("Sequence", "Count"), rows)
