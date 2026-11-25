"""Fastp rendering support through real artifact stores."""

import json
from pathlib import Path

import pytest
from workflow_coda.artifact_store import ArtifactStore, JsonValue
from workflow_coda.context import RenderContext
from workflow_coda.errors import ArtifactReadError
from workflow_coda.manifest import MANIFEST_SCHEMA_VERSION

from coda_bio_plugin.fastp.parser import (
    FastpFilteringResult,
    FastpInsertSize,
    FastpSummary,
    FastpSummaryMetrics,
)
from coda_bio_plugin.fastp.rendering import (
    caption_html,
    filtering_rows,
    insert_size_rows,
    parse_parameters,
    read_report,
    selected_read,
    summary_rows,
)


def context(
    tmp_path: Path,
    data: bytes,
    *,
    fmt: str = "bio.fastp",
) -> RenderContext:
    (tmp_path / "fastp.json").write_bytes(data)
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "producer": {"name": "synthetic", "version": "1"},
        "artifacts": [
            {
                "id": "fastp",
                "type": "org.example.fastp",
                "schema_version": "1.0",
                "path": "fastp.json",
                "format": fmt,
                "status": "complete",
            }
        ],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return RenderContext(store=ArtifactStore.from_manifest_file(path))


def test_curve_section_is_validated_with_common_parameters() -> None:
    spec = parse_parameters(
        "bio.fastp_quality_curves",
        {
            "artifact": "org.example.fastp",
            "section": "read2_after_filtering",
            "include_table": True,
            "caption": "Author caption",
        },
        supports_table=True,
        requires_section=True,
    )
    assert spec.section == "read2_after_filtering"
    assert spec.include_table is True
    assert spec.caption == "Author caption"


@pytest.mark.parametrize("section", [None, "", "summary", "Read1", 1, True])
def test_invalid_curve_sections_are_rejected(section: JsonValue) -> None:
    parameters: dict[str, JsonValue] = {"artifact": "org.example.fastp"}
    if section is not None:
        parameters["section"] = section

    with pytest.raises(ValueError, match="parameter 'section'"):
        parse_parameters(
            "bio.fastp_quality_curves",
            parameters,
            supports_table=True,
            requires_section=True,
        )


def test_non_curve_component_rejects_section() -> None:
    with pytest.raises(ValueError, match="section"):
        parse_parameters(
            "bio.fastp_overview",
            {
                "artifact": "org.example.fastp",
                "section": "read1_before_filtering",
            },
            supports_table=False,
        )


def test_empty_json_parses_without_completeness_checks(tmp_path: Path) -> None:
    spec = parse_parameters(
        "bio.fastp_overview",
        {"artifact": "org.example.fastp"},
        supports_table=False,
    )
    report = read_report(context(tmp_path, b"{}"), "bio.fastp_overview", spec)
    assert report.sections == frozenset()
    assert selected_read(report, "read1_before_filtering") is None


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"{", "not valid JSON"),
        (b'{"future": NaN}', "not valid JSON"),
        (b'{"future": Infinity}', "not valid JSON"),
        (b"[]", "not valid bio.fastp data"),
        (b'{"duplication": {"rate": 1.1}}', "not valid bio.fastp data"),
        (b"\xff", "not valid UTF-8"),
    ],
)
def test_read_failures_keep_actionable_errors(
    tmp_path: Path,
    data: bytes,
    message: str,
) -> None:
    spec = parse_parameters(
        "bio.fastp_overview",
        {"artifact": "org.example.fastp"},
        supports_table=False,
    )
    with pytest.raises(ArtifactReadError, match=message) as caught:
        read_report(context(tmp_path, data), "bio.fastp_overview", spec)
    assert caught.value.__cause__ is not None


def test_format_is_checked_before_parsing(tmp_path: Path) -> None:
    spec = parse_parameters(
        "bio.fastp_overview",
        {"artifact": "org.example.fastp"},
        supports_table=False,
    )
    with pytest.raises(ValueError, match="expected 'bio.fastp'"):
        read_report(
            context(tmp_path, b"bad", fmt="txt"),
            "bio.fastp_overview",
            spec,
        )


def test_filtering_table_distinguishes_absent_and_zero_optional_count() -> None:
    assert len(filtering_rows(FastpFilteringResult(10, 0, 0, 0))) == 4
    assert filtering_rows(FastpFilteringResult(10, 0, 0, 0, 0))[-1] == (
        "Too long",
        "0",
    )


def test_insert_size_table_preserves_zero_bins_and_excludes_unknown() -> None:
    assert insert_size_rows(FastpInsertSize(1, 99, (0, 3, 0))) == (
        ("0", "0"),
        ("1", "3"),
        ("2", "0"),
    )


def test_summary_distinguishes_missing_mate_length_from_zero() -> None:
    before = FastpSummaryMetrics(
        total_reads=0,
        total_bases=0,
        q20_bases=0,
        q30_bases=0,
        q20_rate=0,
        q30_rate=0,
        read1_mean_length=0,
        gc_content=0,
    )
    after = FastpSummaryMetrics(
        total_reads=0,
        total_bases=0,
        q20_bases=0,
        q30_bases=0,
        q20_rate=0,
        q30_rate=0,
        read1_mean_length=0,
        gc_content=0,
        read2_mean_length=0,
    )
    assert summary_rows(FastpSummary(before, after))[-1] == (
        "Read 2 mean length (bp)",
        "Not reported",
        "0",
    )


def test_caption_is_escaped() -> None:
    assert caption_html("<caption>&") == (
        '<p class="coda-bio__caption">&lt;caption&gt;&amp;</p>'
    )
