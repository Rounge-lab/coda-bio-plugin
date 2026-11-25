"""Synthetic figure data and presentation-only theme updates."""

import sys

import pytest
from workflow_coda.errors import RenderError
from workflow_coda.theme import DEFAULT_THEME_PAIR, FigureTheme

from coda_bio_plugin.fastp.figures import (
    CONTENT_NAMES,
    QUALITY_NAMES,
    build_content_curves,
    build_filtering_result,
    build_insert_size,
    build_quality_curves,
    filtering_counts,
)
from coda_bio_plugin.fastp.parser import (
    FastpFilteringResult,
    FastpInsertSize,
    FastpRead,
)


def read_section() -> FastpRead:
    return FastpRead(
        total_reads=10,
        total_bases=20,
        q20_bases=20,
        q30_bases=18,
        q40_bases=None,
        total_cycles=2,
        quality_curves={
            "A": (31.0, 45.0),
            "T": (32.0, 44.0),
            "C": (33.0, 43.0),
            "G": (34.0, 42.0),
            "mean": (32.5, 43.5),
        },
        content_curves={
            "A": (0.1, 0.2),
            "T": (0.2, 0.1),
            "C": (0.3, 0.4),
            "G": (0.4, 0.3),
            "N": (0.0, 0.0),
            "GC": (0.7, 0.7),
        },
        kmer_count=None,
    )


def test_filtering_counts_preserve_optional_absence() -> None:
    result = FastpFilteringResult(
        passed_filter_reads=10,
        low_quality_reads=2,
        too_many_n_reads=3,
        too_short_reads=4,
    )
    assert filtering_counts(result) == (
        ("Passed filter", 10),
        ("Low quality", 2),
        ("Too many Ns", 3),
        ("Too short", 4),
    )

    figure, description, _ = build_filtering_result(DEFAULT_THEME_PAIR, result)
    payload = figure.to_plotly_json()
    trace = payload["data"][0]

    assert trace["type"] == "bar"
    assert list(trace["y"]) == [10, 2, 3, 4]
    assert "Too long" not in trace["x"]
    assert payload["layout"]["xaxis"]["type"] == "category"
    assert "sum of reported counts: 19" in description


def test_optional_zero_count_is_not_omitted() -> None:
    result = FastpFilteringResult(
        passed_filter_reads=10,
        low_quality_reads=0,
        too_many_n_reads=0,
        too_short_reads=0,
        too_long_reads=0,
    )
    figure, _, _ = build_filtering_result(DEFAULT_THEME_PAIR, result)
    trace = figure.to_plotly_json()["data"][0]

    assert list(trace["x"])[-1] == "Too long"
    assert list(trace["y"]) == [10, 0, 0, 0, 0]


def test_insert_size_preserves_indices_counts_and_unknown_metadata() -> None:
    result = FastpInsertSize(
        peak=3,
        unknown=99,
        histogram=(0, 2, 0, 7, 0),
    )
    figure, description, _ = build_insert_size(DEFAULT_THEME_PAIR, result)
    payload = figure.to_plotly_json()
    trace = payload["data"][0]

    assert trace["type"] == "bar"
    assert list(trace["x"]) == [0, 1, 2, 3, 4]
    assert list(trace["y"]) == [0, 2, 0, 7, 0]
    assert payload["layout"]["bargap"] == 0
    assert payload["layout"]["xaxis"]["type"] == "linear"
    assert "reported peak: 3 bp" in description
    assert "reported unknown count: 99" in description
    assert "not plotted as an insert-size bin" in description


def test_quality_curves_preserve_scores_and_use_one_based_cycles() -> None:
    read = read_section()
    figure, description, _ = build_quality_curves(DEFAULT_THEME_PAIR, read)
    payload = figure.to_plotly_json()
    traces = payload["data"]

    assert [trace["name"] for trace in traces] == ["A", "T", "C", "G", "Mean"]
    for name, trace in zip(QUALITY_NAMES, traces, strict=True):
        assert trace["type"] == "scatter"
        assert trace["mode"] == "lines"
        assert list(trace["x"]) == [1, 2]
        assert list(trace["y"]) == list(read.quality_curves[name])

    assert list(traces[0]["y"])[1] == 45
    assert "range" not in payload["layout"]["yaxis"]
    assert "shapes" not in payload["layout"]
    assert "2 supplied cycles" in description
    assert "status" not in description


def test_content_curves_convert_fractions_to_percent_without_stacking() -> None:
    read = read_section()
    figure, description, _ = build_content_curves(DEFAULT_THEME_PAIR, read)
    payload = figure.to_plotly_json()
    traces = payload["data"]

    assert [trace["name"] for trace in traces] == list(CONTENT_NAMES)
    for name, trace in zip(CONTENT_NAMES, traces, strict=True):
        assert list(trace["x"]) == [1, 2]
        assert list(trace["y"]) == pytest.approx(
            [value * 100 for value in read.content_curves[name]]
        )
        assert "stackgroup" not in trace

    assert payload["layout"]["yaxis"]["range"] == [0, 100]
    assert "fractions are displayed as percentages" in description
    assert read.content_curves["GC"] == (0.7, 0.7)


def assert_presentation_only(binding: FigureTheme, trace_count: int) -> None:
    assert set(binding.light.layout) == set(binding.dark.layout)
    assert len(binding.light.traces) == trace_count
    assert len(binding.dark.traces) == trace_count

    for light, dark in zip(
        binding.light.traces,
        binding.dark.traces,
        strict=True,
    ):
        assert set(light) == set(dark)

    for theme, style in (
        (DEFAULT_THEME_PAIR.light, binding.light),
        (DEFAULT_THEME_PAIR.dark, binding.dark),
    ):
        assert style.layout["font.family"] == theme.font_body
        assert style.layout["font.color"] == theme.text_on(theme.colors["surface"])

        assert not {
            "xaxis.range",
            "yaxis.range",
            "xaxis.autorange",
            "yaxis.autorange",
            "xaxis.type",
            "yaxis.type",
            "xaxis.fixedrange",
            "yaxis.fixedrange",
            "xaxis.categoryarray",
            "xaxis.categoryorder",
        }.intersection(style.layout)

        for trace in style.traces:
            assert not {
                "x",
                "y",
                "name",
                "visible",
                "mode",
                "stackgroup",
            }.intersection(trace)


@pytest.mark.parametrize("kind", ["filtering", "insert-size", "quality", "content"])
def test_all_bindings_preserve_data_and_axis_policy(kind: str) -> None:
    if kind == "filtering":
        figure, _, binding = build_filtering_result(
            DEFAULT_THEME_PAIR,
            FastpFilteringResult(10, 2, 3, 4),
        )
        trace_count = 1
    elif kind == "insert-size":
        figure, _, binding = build_insert_size(
            DEFAULT_THEME_PAIR,
            FastpInsertSize(1, 3, (0, 2, 0)),
        )
        trace_count = 1
    elif kind == "quality":
        figure, _, binding = build_quality_curves(
            DEFAULT_THEME_PAIR,
            read_section(),
        )
        trace_count = len(QUALITY_NAMES)
    else:
        figure, _, binding = build_content_curves(
            DEFAULT_THEME_PAIR,
            read_section(),
        )
        trace_count = len(CONTENT_NAMES)

    assert len(figure.to_plotly_json()["data"]) == trace_count
    assert_presentation_only(binding, trace_count)


@pytest.mark.parametrize("content", [False, True], ids=["quality", "content"])
def test_line_colors_follow_both_modes(content: bool) -> None:
    builder = build_content_curves if content else build_quality_curves
    figure, _, binding = builder(DEFAULT_THEME_PAIR, read_section())
    traces = figure.to_plotly_json()["data"]

    for index, trace in enumerate(traces):
        color = DEFAULT_THEME_PAIR.light.series[
            index % len(DEFAULT_THEME_PAIR.light.series)
        ]
        assert trace["line"]["color"] == color
        assert trace["marker"]["color"] == color

    for theme, style in (
        (DEFAULT_THEME_PAIR.light, binding.light),
        (DEFAULT_THEME_PAIR.dark, binding.dark),
    ):
        for index, update in enumerate(style.traces):
            color = theme.series[index % len(theme.series)]
            assert update["line.color"] == color
            assert update["marker.color"] == color


def test_bar_colors_follow_both_modes() -> None:
    figure, _, binding = build_insert_size(
        DEFAULT_THEME_PAIR,
        FastpInsertSize(1, 0, (0, 2)),
    )
    assert (
        figure.to_plotly_json()["data"][0]["marker"]["color"]
        == DEFAULT_THEME_PAIR.light.series[0]
    )
    for theme, style in (
        (DEFAULT_THEME_PAIR.light, binding.light),
        (DEFAULT_THEME_PAIR.dark, binding.dark),
    ):
        assert style.traces[0]["marker.color"] == theme.series[0]


def test_missing_plotly_teaches(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(sys.modules):
        if key == "plotly" or key.startswith("plotly."):
            monkeypatch.delitem(sys.modules, key)
    monkeypatch.setitem(sys.modules, "plotly", None)

    with pytest.raises(
        RenderError,
        match="fastp charts require plotly.*install plotly and build again",
    ) as caught:
        build_quality_curves(DEFAULT_THEME_PAIR, read_section())

    assert caught.value.__cause__ is not None
