"""Figure data and the installed-plugin CLI seam."""

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from workflow_coda.cli import main
from workflow_coda.errors import RenderError
from workflow_coda.layout import LAYOUT_SCHEMA_VERSION
from workflow_coda.manifest import MANIFEST_SCHEMA_VERSION
from workflow_coda.theme import DEFAULT_THEME

from coda_bio_plugin.fastqc import figures
from coda_bio_plugin.fastqc.parser import parse_fastqc
from coda_bio_plugin.plugin import get_plugin

EXAMPLE = Path("docs/examples/fastqc/fastqc_data.txt")


def module(name: str) -> Any:
    report = parse_fastqc(EXAMPLE.read_text(encoding="utf-8"))
    found = report.find_module(name)
    assert found is not None
    return found


def test_precomputed_quality_boxes_and_guides() -> None:
    data = module("Per base sequence quality")
    figure, description = figures.build_per_base_sequence_quality(DEFAULT_THEME, data)
    traces = figure.to_plotly_json()["data"]
    assert traces[0]["type"] == "box"
    assert traces[0]["boxpoints"] is False
    assert traces[0]["q1"][0] == 34.0
    assert traces[0]["lowerfence"][0] == 28.0
    assert traces[0]["upperfence"][0] == 34.0
    assert traces[1]["mode"] == "lines+markers"
    assert traces[0]["x"][9] == "10-14"
    layout = figure.to_plotly_json()["layout"]
    assert layout["yaxis"]["range"][0] <= 0
    assert layout["yaxis"]["range"][1] >= 40
    assert [shape["fillcolor"] for shape in layout["shapes"]] == [
        DEFAULT_THEME.colors["danger"],
        DEFAULT_THEME.colors["warning"],
        DEFAULT_THEME.colors["success"],
    ]
    assert "reported FastQC status: Pass" in description


def test_reordered_columns_and_fractional_counts() -> None:
    report = parse_fastqc(
        "##FastQC\t1\n"
        ">>Per sequence GC content\twarn\n"
        "#GC Content\tExtra\tCount\n"
        "28\tkept\t29.5\n"
        "29\tkept\t60.0\n"
        ">>END_MODULE\n"
    )
    data = report.find_module("Per sequence GC content")
    assert data is not None
    figure, description = figures.build_per_sequence_gc_content(DEFAULT_THEME, data)
    traces = figure.to_plotly_json()["data"]
    assert len(traces) == 1
    assert traces[0]["type"] == "bar"
    assert list(traces[0]["x"]) == [28.0, 29.0]
    assert list(traces[0]["y"]) == [29.5, 60.0]
    assert traces[0]["marker"]["color"] == DEFAULT_THEME.colors["warning"]
    assert "sum of reported counts: 89.5" in description
    assert "reads" not in description


def test_heatmap_and_grouped_bars() -> None:
    content = module("Per base sequence content")
    figure, description = figures.build_per_base_sequence_content(
        DEFAULT_THEME, content
    )
    trace = figure.to_plotly_json()["data"][0]
    assert trace["type"] == "heatmap"
    assert list(trace["y"]) == ["G", "A", "T", "C"]
    assert trace["zmin"] == 0 and trace["zmax"] == 100
    assert trace["colorscale"][0][1] == DEFAULT_THEME.colors["surface"]
    assert trace["colorscale"][-1][1] == DEFAULT_THEME.colors["primary"]
    assert "4 series: G, A, T, C" in description

    duplication = module("Sequence Duplication Levels")
    figure, description = figures.build_sequence_duplication_levels(
        DEFAULT_THEME, duplication
    )
    payload = figure.to_plotly_json()
    assert payload["layout"]["barmode"] == "group"
    assert len(payload["data"]) == 2
    assert payload["data"][0]["x"][9] == "&gt;10"
    assert payload["data"][0]["marker"]["color"] == DEFAULT_THEME.series[0]
    assert payload["data"][1]["marker"]["color"] == DEFAULT_THEME.series[1]
    assert "2 series" in description


def test_missing_plotly_teaches(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(sys.modules):
        if key == "plotly" or key.startswith("plotly."):
            monkeypatch.delitem(sys.modules, key)
    monkeypatch.setitem(sys.modules, "plotly", None)
    with pytest.raises(RenderError, match="install plotly and build again") as caught:
        figures.build_per_base_n_content(DEFAULT_THEME, module("Per base N content"))
    assert caught.value.__cause__ is not None


def test_cli_seam_all_components_and_repeated_chart(tmp_path: Path) -> None:
    (tmp_path / "fastqc_data.txt").write_text(
        EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8"
    )
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "producer": {"name": "fastqc-seam", "version": "1"},
        "artifacts": [
            {
                "id": "fastqc",
                "type": "org.example.fastqc",
                "schema_version": "1.0",
                "path": "fastqc_data.txt",
                "format": "bio.fastqc",
                "status": "complete",
            }
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    ids = [item.id for item in get_plugin().components]
    placements = "".join(
        f"      - id: {id_}\n"
        "        parameters:\n"
        "          artifact: org.example.fastqc\n"
        + (
            "          include_table: true\n"
            if id_
            in {
                "bio.fastqc_basic_statistics",
                "bio.fastqc_per_base_sequence_quality",
            }
            else ""
        )
        for id_ in [*ids, "bio.fastqc_per_base_n_content"]
    )
    layout = tmp_path / "layout.yaml"
    layout.write_text(
        f'schema_version: "{LAYOUT_SCHEMA_VERSION}"\n'
        "title: FastQC\n"
        "tabs:\n"
        "  - title: Results\n"
        "    components:\n"
        f"{placements}"
        "  - title: Diagnostics\n"
        "    components:\n"
        "      - type: diagnostics\n",
        encoding="utf-8",
    )
    output = tmp_path / "report.html"
    main(["build", str(manifest_path), str(layout), "-o", str(output)])
    page = output.read_text(encoding="utf-8")
    for id_ in ids:
        assert f'data-component="{id_}"' in page
        assert page.count(f"/* {id_} */") == 1
    assert page.count('data-component="bio.fastqc_per_base_n_content"') == 2
    assert page.count('class="coda-figure"') == 9
    assert page.count("<summary>Data table</summary>") == 1
    assert "VC1_1.fastq.gz" in page
    assert "Plotly.newPlot" in page
