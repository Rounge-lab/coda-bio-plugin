"""Non-chart fastp components through registered declarations and real stores."""

import json
import sys
from pathlib import Path

import pytest
from workflow_coda.artifact_store import ArtifactStore, JsonValue
from workflow_coda.cli import main
from workflow_coda.components import (
    ComponentChrome,
    ComponentStatus,
    PlacementInfo,
    ReportComponent,
)
from workflow_coda.context import RenderContext
from workflow_coda.errors import ArtifactReadError
from workflow_coda.icons import IconLibrary, IconSource
from workflow_coda.layout import LAYOUT_SCHEMA_VERSION
from workflow_coda.manifest import MANIFEST_SCHEMA_VERSION

from coda_bio_plugin.fastp.components import FASTP_COMPONENTS
from coda_bio_plugin.plugin import get_plugin

TYPE = "org.example.fastp"

NON_CHART_COMPONENTS = tuple(
    item
    for item in FASTP_COMPONENTS
    if item.id
    in {
        "bio.fastp_overview",
        "bio.fastp_duplication",
        "bio.fastp_adapter_cutting",
    }
)


def context(
    tmp_path: Path,
    payload: JsonValue,
    *,
    status: str = "complete",
    fmt: str = "bio.fastp",
) -> RenderContext:
    (tmp_path / "fastp.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "producer": {"name": "synthetic", "version": "1"},
        "artifacts": [
            {
                "id": "fastp",
                "type": TYPE,
                "schema_version": "1.0",
                "path": "fastp.json",
                "format": fmt,
                "status": status,
            }
        ],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return RenderContext(
        store=ArtifactStore.from_manifest_file(path),
        icons=IconLibrary((IconSource.for_plugin("core", "workflow_coda.core"),)),
    )


def metrics() -> dict[str, JsonValue]:
    return {
        "total_reads": 0,
        "total_bases": 0,
        "q20_bases": 0,
        "q30_bases": 0,
        "q20_rate": 0,
        "q30_rate": 0,
        "read1_mean_length": 0,
        "gc_content": 0,
    }


def payload() -> dict[str, JsonValue]:
    return {
        "summary": {
            "fastp_version": "<version>&",
            "sequencing": "<single-end>&",
            "before_filtering": metrics(),
            "after_filtering": metrics(),
        },
        "duplication": {"rate": 0.99},
        "adapter_cutting": {
            "adapter_trimmed_reads": 0,
            "adapter_trimmed_bases": 0,
            "read1_adapter_sequence": "<adapter>&",
            "read1_adapter_counts": {"<sequence>&": 3},
            "read2_adapter_counts": {},
        },
    }


def test_registration() -> None:
    registered = tuple(
        item for item in get_plugin().components if item.id.startswith("bio.fastp_")
    )
    assert registered == FASTP_COMPONENTS
    assert all(item.chrome is ComponentChrome.CARD for item in registered)
    assert {item.id for item in registered} == {
        "bio.fastp_overview",
        "bio.fastp_duplication",
        "bio.fastp_adapter_cutting",
        "bio.fastp_filtering_result",
        "bio.fastp_insert_size",
        "bio.fastp_quality_curves",
        "bio.fastp_content_curves",
    }


@pytest.mark.parametrize("item", NON_CHART_COMPONENTS, ids=lambda item: item.id)
def test_registered_components_render_without_plotly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    item: ReportComponent,
) -> None:
    ctx = context(tmp_path, payload())
    monkeypatch.setitem(sys.modules, "plotly", None)

    result = item.render(
        ctx,
        PlacementInfo(title="Ignored placement title"),
        {"artifact": TYPE, "caption": "<caption>&"},
    )
    assert result.status is ComponentStatus.OK
    assert result.html is not None
    assert "Ignored placement title" not in result.html
    assert "&lt;caption&gt;&amp;" in result.html
    assert result.html.count("&lt;caption&gt;&amp;") == 1
    assert "coda-figure" not in result.html

    if item.id == "bio.fastp_overview":
        assert "&lt;version&gt;&amp;" in result.html
        assert "&lt;single-end&gt;&amp;" in result.html
        assert "Before filtering" in result.html
        assert "After filtering" in result.html
        assert '<div class="coda-table" data-copy-rows="all">' in result.html
    elif item.id == "bio.fastp_duplication":
        assert "99.00%" in result.html
        assert "<table" not in result.html
    else:
        assert "&lt;adapter&gt;&amp;" in result.html
        assert "&lt;sequence&gt;&amp;" in result.html
        assert "No adapter-count entries were reported." in result.html


@pytest.mark.parametrize("item", NON_CHART_COMPONENTS, ids=lambda item: item.id)
def test_missing_sections_are_unavailable(
    tmp_path: Path,
    item: ReportComponent,
) -> None:
    result = item.render(
        context(tmp_path, {}),
        PlacementInfo(title="Ignored"),
        {"artifact": TYPE},
    )
    assert result.status is ComponentStatus.UNAVAILABLE
    assert result.message is not None
    assert "carries no section" in result.message


@pytest.mark.parametrize("item", NON_CHART_COMPONENTS, ids=lambda item: item.id)
def test_failed_artifacts_are_unavailable(
    tmp_path: Path,
    item: ReportComponent,
) -> None:
    result = item.render(
        context(tmp_path, {}, status="failed"),
        PlacementInfo(title="Ignored"),
        {"artifact": TYPE},
    )
    assert result.status is ComponentStatus.UNAVAILABLE


@pytest.mark.parametrize(
    "parameters",
    [
        {},
        {"artifact": None},
        {"artifact": TYPE, "caption": None},
        {"artifact": TYPE, "include_table": True},
        {"artifact": TYPE, "section": "read1_before_filtering"},
        {"artifact": TYPE, "artifct": "x"},
    ],
)
@pytest.mark.parametrize("item", NON_CHART_COMPONENTS, ids=lambda item: item.id)
def test_parameters_are_validated_before_store_access(
    tmp_path: Path,
    item: ReportComponent,
    parameters: dict[str, JsonValue],
) -> None:
    with pytest.raises(ValueError, match=item.id):
        item.render(
            context(tmp_path, {}, status="failed"),
            PlacementInfo(title="Ignored"),
            parameters,
        )


def test_absent_adapter_counts_are_not_reported_as_empty(tmp_path: Path) -> None:
    ctx = context(
        tmp_path,
        {
            "adapter_cutting": {
                "adapter_trimmed_reads": 0,
                "adapter_trimmed_bases": 0,
            }
        },
    )
    item = next(
        item for item in FASTP_COMPONENTS if item.id == "bio.fastp_adapter_cutting"
    )
    result = item.render(
        ctx,
        PlacementInfo(title="Ignored"),
        {"artifact": TYPE},
    )
    assert result.html is not None
    assert result.html.count("Adapter counts were not reported.") == 2
    assert "No adapter-count entries were reported." not in result.html


def test_wrong_format_and_invalid_data_remain_errors(tmp_path: Path) -> None:
    item = FASTP_COMPONENTS[0]
    with pytest.raises(ValueError, match="expected 'bio.fastp'"):
        item.render(
            context(tmp_path, {}, fmt="txt"),
            PlacementInfo(title="Ignored"),
            {"artifact": TYPE},
        )

    with pytest.raises(ArtifactReadError, match="not valid bio.fastp data"):
        item.render(
            context(tmp_path, {"summary": None}),
            PlacementInfo(title="Ignored"),
            {"artifact": TYPE},
        )


CHART_COMPONENTS = tuple(
    item for item in FASTP_COMPONENTS if item not in NON_CHART_COMPONENTS
)

CURVE_IDS = {
    "bio.fastp_quality_curves",
    "bio.fastp_content_curves",
}

DATA_TABLE_TITLE = '<span class="coda-bio__disclosure-title">Data table</span>'


def chart_payload(*, cycles: int = 2, empty_histogram: bool = False) -> JsonValue:
    return {
        "filtering_result": {
            "passed_filter_reads": 0,
            "low_quality_reads": 0,
            "too_many_N_reads": 0,
            "too_short_reads": 0,
            "too_long_reads": 0,
        },
        "insert_size": {
            "peak": 1,
            "unknown": 99,
            "histogram": [] if empty_histogram else [0, 3, 0],
        },
        "read1_before_filtering": {
            "total_reads": 0,
            "total_bases": 0,
            "q20_bases": 0,
            "q30_bases": 0,
            "total_cycles": cycles,
            "quality_curves": {
                name: [35.0] * cycles for name in ("A", "T", "C", "G", "mean")
            },
            "content_curves": {
                name: [0.25] * cycles for name in ("A", "T", "C", "G", "N", "GC")
            },
        },
    }


def chart_parameters(
    item: ReportComponent,
    *,
    include_table: bool = False,
) -> dict[str, JsonValue]:
    parameters: dict[str, JsonValue] = {
        "artifact": TYPE,
        "caption": "<caption>&",
        "include_table": include_table,
    }
    if item.id in CURVE_IDS:
        parameters["section"] = "read1_before_filtering"
    return parameters


@pytest.mark.parametrize("item", CHART_COMPONENTS, ids=lambda item: item.id)
@pytest.mark.parametrize("include_table", [False, True])
def test_charts_and_optional_complete_tables(
    tmp_path: Path,
    item: ReportComponent,
    include_table: bool,
) -> None:
    result = item.render(
        context(tmp_path, chart_payload()),
        PlacementInfo(title="Ignored"),
        chart_parameters(item, include_table=include_table),
    )
    assert result.status is ComponentStatus.OK
    assert result.html is not None
    assert result.html.count('class="coda-figure"') == 1
    assert result.html.count('data-coda-figure-theme="') == 1
    assert result.html.count("&lt;caption&gt;&amp;") == 1
    assert "Ignored" not in result.html
    assert ("<table" in result.html) is include_table
    assert (DATA_TABLE_TITLE in result.html) is include_table

    if include_table:
        assert '<div class="coda-table" data-copy-rows="all">' in result.html
        assert "data-max-visible-rows" not in result.html
        assert "coda-table__caption" not in result.html

    if item.id == "bio.fastp_insert_size":
        assert "Reported unknown count</dt><dd>99</dd>" in result.html
        assert "not plotted as an insert-size bin" in result.html
    elif item.id in CURVE_IDS:
        assert "read1 before filtering" in result.html


@pytest.mark.parametrize("item", CHART_COMPONENTS, ids=lambda item: item.id)
def test_chart_missing_sections_are_unavailable(
    tmp_path: Path,
    item: ReportComponent,
) -> None:
    result = item.render(
        context(tmp_path, {}),
        PlacementInfo(title="Ignored"),
        chart_parameters(item),
    )
    assert result.status is ComponentStatus.UNAVAILABLE
    assert result.message is not None
    assert "carries no section" in result.message


@pytest.mark.parametrize(
    "item",
    tuple(item for item in CHART_COMPONENTS if item.id in CURVE_IDS),
    ids=lambda item: item.id,
)
@pytest.mark.parametrize("include_table", [False, True])
def test_zero_cycle_curves_do_not_import_plotly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    item: ReportComponent,
    include_table: bool,
) -> None:
    ctx = context(tmp_path, chart_payload(cycles=0))
    monkeypatch.setitem(sys.modules, "plotly", None)
    result = item.render(
        ctx,
        PlacementInfo(title="Ignored"),
        chart_parameters(item, include_table=include_table),
    )
    assert result.status is ComponentStatus.OK
    assert result.html is not None
    assert "This read section contains no cycles." in result.html
    assert "coda-figure" not in result.html
    assert "data-coda-figure-theme" not in result.html
    assert ("<table" in result.html) is include_table


@pytest.mark.parametrize("include_table", [False, True])
def test_empty_histogram_preserves_metadata_without_plotly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    include_table: bool,
) -> None:
    item = next(item for item in CHART_COMPONENTS if item.id == "bio.fastp_insert_size")
    ctx = context(tmp_path, chart_payload(empty_histogram=True))
    monkeypatch.setitem(sys.modules, "plotly", None)
    result = item.render(
        ctx,
        PlacementInfo(title="Ignored"),
        chart_parameters(item, include_table=include_table),
    )
    assert result.status is ComponentStatus.OK
    assert result.html is not None
    assert "contains no insert-size histogram bins" in result.html
    assert "Reported peak (bp)</dt><dd>1</dd>" in result.html
    assert "Reported unknown count</dt><dd>99</dd>" in result.html
    assert "coda-figure" not in result.html
    assert ("<table" in result.html) is include_table


@pytest.mark.parametrize("item", CHART_COMPONENTS, ids=lambda item: item.id)
@pytest.mark.parametrize("value", [None, "true", 1])
def test_chart_table_parameter_errors_precede_store_access(
    tmp_path: Path,
    item: ReportComponent,
    value: JsonValue,
) -> None:
    parameters = chart_parameters(item)
    parameters["include_table"] = value
    with pytest.raises(ValueError, match="include_table"):
        item.render(
            context(tmp_path, {}, status="failed"),
            PlacementInfo(title="Ignored"),
            parameters,
        )


@pytest.mark.parametrize(
    "item",
    tuple(item for item in CHART_COMPONENTS if item.id in CURVE_IDS),
    ids=lambda item: item.id,
)
@pytest.mark.parametrize("section", [None, "", "summary", 1])
def test_curve_section_errors_precede_store_access(
    tmp_path: Path,
    item: ReportComponent,
    section: JsonValue,
) -> None:
    parameters = chart_parameters(item)
    if section is None:
        del parameters["section"]
    else:
        parameters["section"] = section
    with pytest.raises(ValueError, match="parameter 'section'"):
        item.render(
            context(tmp_path, {}, status="failed"),
            PlacementInfo(title="Ignored"),
            parameters,
        )


def test_cli_build_all_fastp_components_and_repeated_chart(tmp_path: Path) -> None:
    combined = payload()
    charts = chart_payload()
    assert isinstance(charts, dict)
    combined.update(charts)

    # The real-store helper writes the manifest and artifact.
    context(tmp_path, combined)

    placements = ""
    for item in (*FASTP_COMPONENTS, CHART_COMPONENTS[0]):
        placements += (
            f"      - id: {item.id}\n        parameters:\n          artifact: {TYPE}\n"
        )
        if item in CHART_COMPONENTS:
            placements += "          include_table: true\n"
        if item.id in CURVE_IDS:
            placements += "          section: read1_before_filtering\n"

    layout = tmp_path / "layout.yaml"
    layout.write_text(
        f'schema_version: "{LAYOUT_SCHEMA_VERSION}"\n'
        "title: fastp\n"
        "theme:\n"
        "  light: default\n"
        "  dark: default-dark\n"
        "tabs:\n"
        "  - title: Results\n"
        "    components:\n"
        f"{placements}",
        encoding="utf-8",
    )
    output = tmp_path / "report.html"
    main(
        [
            "build",
            str(tmp_path / "manifest.json"),
            str(layout),
            "-o",
            str(output),
        ]
    )
    page = output.read_text(encoding="utf-8")

    for item in FASTP_COMPONENTS:
        assert f'data-component="{item.id}"' in page
        assert page.count(f"/* {item.id} */") == 1

    repeated = CHART_COMPONENTS[0].id
    assert page.count(f'data-component="{repeated}"') == 2
    assert page.count('class="coda-figure"') == 5
    assert page.count('data-coda-figure-theme="') == 5
    assert page.count(DATA_TABLE_TITLE) == 5
    assert "Plotly.newPlot" in page
    assert "data-coda-bio-table-initialized" in page
    assert "&lt;sequence&gt;&amp;" in page
