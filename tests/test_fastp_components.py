"""Non-chart fastp components through registered declarations and real stores."""

import json
import sys
from pathlib import Path

import pytest
from workflow_coda.artifact_store import ArtifactStore, JsonValue
from workflow_coda.components import (
    ComponentChrome,
    ComponentStatus,
    PlacementInfo,
    ReportComponent,
)
from workflow_coda.context import RenderContext
from workflow_coda.errors import ArtifactReadError
from workflow_coda.icons import IconLibrary, IconSource
from workflow_coda.manifest import MANIFEST_SCHEMA_VERSION

from coda_bio_plugin.fastp.components import FASTP_COMPONENTS
from coda_bio_plugin.plugin import get_plugin

TYPE = "org.example.fastp"


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
    }


@pytest.mark.parametrize("item", FASTP_COMPONENTS, ids=lambda item: item.id)
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


@pytest.mark.parametrize("item", FASTP_COMPONENTS, ids=lambda item: item.id)
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


@pytest.mark.parametrize("item", FASTP_COMPONENTS, ids=lambda item: item.id)
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
@pytest.mark.parametrize("item", FASTP_COMPONENTS, ids=lambda item: item.id)
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
