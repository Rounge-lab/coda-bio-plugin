"""Figure data, paired presentation, and the installed-plugin CLI seam."""

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from workflow_coda.cli import main
from workflow_coda.errors import RenderError
from workflow_coda.layout import LAYOUT_SCHEMA_VERSION
from workflow_coda.manifest import MANIFEST_SCHEMA_VERSION
from workflow_coda.theme import DEFAULT_THEME, DEFAULT_THEME_PAIR

from coda_bio_plugin.fastqc import figures
from coda_bio_plugin.fastqc.parser import FastqcModule, parse_fastqc
from coda_bio_plugin.plugin import get_plugin

EXAMPLE = Path("docs/examples/fastqc/fastqc_data.txt")

CHART_BUILDERS: tuple[tuple[str, figures.FigureBuilder, int], ...] = (
    (
        "Per base sequence quality",
        figures.build_per_base_sequence_quality,
        2,
    ),
    (
        "Per sequence quality scores",
        figures.build_per_sequence_quality_scores,
        1,
    ),
    (
        "Per base sequence content",
        figures.build_per_base_sequence_content,
        1,
    ),
    (
        "Per sequence GC content",
        figures.build_per_sequence_gc_content,
        1,
    ),
    (
        "Per base N content",
        figures.build_per_base_n_content,
        1,
    ),
    (
        "Sequence Length Distribution",
        figures.build_sequence_length_distribution,
        1,
    ),
    (
        "Sequence Duplication Levels",
        figures.build_sequence_duplication_levels,
        2,
    ),
    ("Adapter Content", figures.build_adapter_content, 1),
)


def module(name: str) -> FastqcModule:
    report = parse_fastqc(EXAMPLE.read_text(encoding="utf-8"))
    found = report.find_module(name)
    assert found is not None
    return found


def test_precomputed_quality_boxes_and_guides() -> None:
    data = module("Per base sequence quality")
    figure, description, _ = figures.build_per_base_sequence_quality(
        DEFAULT_THEME_PAIR, data
    )
    payload = figure.to_plotly_json()
    traces = payload["data"]

    assert traces[0]["type"] == "box"
    assert traces[0]["boxpoints"] is False
    assert traces[0]["q1"][0] == 34.0
    assert traces[0]["lowerfence"][0] == 28.0
    assert traces[0]["upperfence"][0] == 34.0
    assert traces[1]["mode"] == "lines+markers"
    assert traces[0]["x"][9] == "10-14"

    layout = payload["layout"]
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
    figure, description, _ = figures.build_per_sequence_gc_content(
        DEFAULT_THEME_PAIR, data
    )
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
    figure, description, _ = figures.build_per_base_sequence_content(
        DEFAULT_THEME_PAIR, content
    )
    trace = figure.to_plotly_json()["data"][0]

    assert trace["type"] == "heatmap"
    assert list(trace["y"]) == ["G", "A", "T", "C"]
    assert trace["zmin"] == 0 and trace["zmax"] == 100
    assert trace["colorscale"][0][1] == DEFAULT_THEME.colors["surface"]
    assert trace["colorscale"][-1][1] == DEFAULT_THEME.colors["success"]
    assert "4 series: G, A, T, C" in description

    duplication = module("Sequence Duplication Levels")
    figure, description, _ = figures.build_sequence_duplication_levels(
        DEFAULT_THEME_PAIR, duplication
    )
    payload = figure.to_plotly_json()

    assert payload["layout"]["barmode"] == "group"
    assert len(payload["data"]) == 2
    assert payload["data"][0]["x"][9] == "&gt;10"
    assert payload["data"][0]["marker"]["color"] == DEFAULT_THEME.series[0]
    assert payload["data"][1]["marker"]["color"] == DEFAULT_THEME.series[1]
    assert "2 series" in description


@pytest.mark.parametrize(
    ("module_name", "builder"),
    [
        (
            "Per base sequence content",
            figures.build_per_base_sequence_content,
        ),
        ("Adapter Content", figures.build_adapter_content),
    ],
    ids=["per-base-sequence-content", "adapter-content"],
)
@pytest.mark.parametrize(
    ("status", "color_token"),
    [
        ("pass", "success"),
        ("warn", "warning"),
        ("fail", "danger"),
    ],
)
def test_heatmap_colors_follow_reported_status_in_both_modes(
    module_name: str,
    builder: figures.FigureBuilder,
    status: str,
    color_token: str,
) -> None:
    data = replace(module(module_name), status=status)
    figure, _, binding = builder(DEFAULT_THEME_PAIR, data)

    trace = figure.to_plotly_json()["data"][0]
    assert trace["colorscale"][0][1] == DEFAULT_THEME.colors["surface"]
    assert trace["colorscale"][-1][1] == DEFAULT_THEME.colors[color_token]

    for theme, style in (
        (DEFAULT_THEME_PAIR.light, binding.light),
        (DEFAULT_THEME_PAIR.dark, binding.dark),
    ):
        ink = theme.text_on(theme.colors["surface"])
        updates = style.traces[0]
        assert updates["colorscale"] == [
            [0, theme.colors["surface"]],
            [1, theme.colors[color_token]],
        ]
        assert updates["colorbar.tickfont.color"] == ink
        assert updates["colorbar.tickfont.family"] == theme.font_body
        assert updates["colorbar.title.font.color"] == ink
        assert updates["colorbar.title.font.family"] == theme.font_body
        assert updates["colorbar.outlinecolor"] == theme.colors["border"]

    assert (
        binding.light.traces[0]["colorscale"] != (binding.dark.traces[0]["colorscale"])
    )


@pytest.mark.parametrize(
    ("module_name", "builder", "trace_count"),
    CHART_BUILDERS,
    ids=[entry[0] for entry in CHART_BUILDERS],
)
def test_all_chart_bindings_cover_both_modes_without_data_updates(
    module_name: str,
    builder: figures.FigureBuilder,
    trace_count: int,
) -> None:
    figure, _, binding = builder(DEFAULT_THEME_PAIR, module(module_name))
    initial = figure.to_plotly_json()

    assert len(initial["data"]) == trace_count
    assert set(binding.light.layout) == set(binding.dark.layout)
    assert len(binding.light.traces) == len(binding.dark.traces)
    for light_trace, dark_trace in zip(
        binding.light.traces, binding.dark.traces, strict=True
    ):
        assert set(light_trace) == set(dark_trace)

    for theme, style in (
        (DEFAULT_THEME_PAIR.light, binding.light),
        (DEFAULT_THEME_PAIR.dark, binding.dark),
    ):
        assert len(style.traces) == trace_count
        assert style.layout["font.family"] == theme.font_body
        assert style.layout["font.color"] == theme.text_on(theme.colors["surface"])
        assert style.layout["paper_bgcolor"] == "rgba(0, 0, 0, 0)"
        assert style.layout["plot_bgcolor"] == "rgba(0, 0, 0, 0)"

        for axis in ("xaxis", "yaxis"):
            for field in ("gridcolor", "linecolor", "zerolinecolor"):
                assert style.layout[f"{axis}.{field}"] == theme.colors["border"]

        assert not {
            "xaxis.range",
            "yaxis.range",
            "xaxis.autorange",
            "yaxis.autorange",
            "xaxis.fixedrange",
            "yaxis.fixedrange",
            "xaxis.type",
            "yaxis.type",
            "xaxis.categoryarray",
            "yaxis.categoryarray",
            "xaxis.categoryorder",
            "yaxis.categoryorder",
        }.intersection(style.layout)
        for trace in style.traces:
            assert not {
                "x",
                "y",
                "z",
                "zmin",
                "zmax",
                "q1",
                "median",
                "q3",
                "lowerfence",
                "upperfence",
                "name",
                "visible",
            }.intersection(trace)


def test_quality_trace_and_guide_colors_follow_both_modes() -> None:
    figure, _, binding = figures.build_per_base_sequence_quality(
        DEFAULT_THEME_PAIR, module("Per base sequence quality")
    )
    assert len(figure.to_plotly_json()["layout"]["shapes"]) == 3

    for theme, style in (
        (DEFAULT_THEME_PAIR.light, binding.light),
        (DEFAULT_THEME_PAIR.dark, binding.dark),
    ):
        ink = theme.text_on(theme.colors["surface"])
        assert style.traces[0]["line.color"] == ink
        assert style.traces[0]["fillcolor"] == "rgba(0, 0, 0, 0)"
        assert style.traces[1]["marker.color"] == ink
        assert style.traces[1]["line.color"] == theme.series[1]

        for index, token in enumerate(("danger", "warning", "success")):
            assert style.layout[f"shapes[{index}].fillcolor"] == (theme.colors[token])
            assert f"shapes[{index}].y0" not in style.layout
            assert f"shapes[{index}].y1" not in style.layout

    assert (
        binding.light.layout["shapes[0].fillcolor"]
        != (binding.dark.layout["shapes[0].fillcolor"])
    )


def test_duplication_series_follow_both_modes() -> None:
    _, _, binding = figures.build_sequence_duplication_levels(
        DEFAULT_THEME_PAIR, module("Sequence Duplication Levels")
    )

    for theme, style in (
        (DEFAULT_THEME_PAIR.light, binding.light),
        (DEFAULT_THEME_PAIR.dark, binding.dark),
    ):
        assert len(style.traces) == 2
        assert style.traces[0]["marker.color"] == theme.series[0]
        assert style.traces[1]["marker.color"] == theme.series[1]


@pytest.mark.parametrize(
    ("module_name", "builder"),
    [
        (name, builder)
        for name, builder, _ in CHART_BUILDERS
        if name
        in {
            "Per sequence quality scores",
            "Per sequence GC content",
            "Per base N content",
            "Sequence Length Distribution",
        }
    ],
)
@pytest.mark.parametrize(
    ("status", "token"),
    [("pass", "success"), ("warn", "warning"), ("fail", "danger")],
)
def test_bar_colors_follow_reported_status_in_both_modes(
    module_name: str,
    builder: figures.FigureBuilder,
    status: str,
    token: str,
) -> None:
    data = replace(module(module_name), status=status)
    figure, _, binding = builder(DEFAULT_THEME_PAIR, data)

    assert (
        figure.to_plotly_json()["data"][0]["marker"]["color"]
        == (DEFAULT_THEME.colors[token])
    )
    for theme, style in (
        (DEFAULT_THEME_PAIR.light, binding.light),
        (DEFAULT_THEME_PAIR.dark, binding.dark),
    ):
        assert style.traces[0]["marker.color"] == theme.colors[token]


def test_missing_plotly_teaches(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(sys.modules):
        if key == "plotly" or key.startswith("plotly."):
            monkeypatch.delitem(sys.modules, key)
    monkeypatch.setitem(sys.modules, "plotly", None)

    with pytest.raises(RenderError, match="install plotly and build again") as caught:
        figures.build_per_base_n_content(
            DEFAULT_THEME_PAIR, module("Per base N content")
        )

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
            if id_ == "bio.fastqc_per_base_sequence_quality"
            else ""
        )
        for id_ in [*ids, "bio.fastqc_per_base_n_content"]
    )
    layout = tmp_path / "layout.yaml"
    layout.write_text(
        f'schema_version: "{LAYOUT_SCHEMA_VERSION}"\n'
        "title: FastQC\n"
        "theme:\n"
        "  light: default\n"
        "  dark: default-dark\n"
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
    assert page.count('data-coda-figure-theme="') == 9
    assert (
        page.count('<span class="coda-bio-fastqc__disclosure-title">Data table</span>')
        == 1
    )
    assert '<span class="coda-bio-fastqc__dropdown"><svg' in page

    # Disclosures embed their SVG independently of state navigation chrome.
    assert '<template id="coda-dropdown-icon">' not in page
    assert "VC1_1.fastq.gz" in page
    assert "Plotly.newPlot" in page
    assert "border-left-color: var(--coda-success);" in page
    assert "border-left-color: var(--coda-warning);" in page
    assert "border-left-color: var(--coda-danger);" in page
