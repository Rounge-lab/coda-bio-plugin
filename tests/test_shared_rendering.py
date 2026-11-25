from workflow_coda.theme import DEFAULT_THEME_PAIR

from coda_bio_plugin.shared.assets import guard_core_table_js
from coda_bio_plugin.shared.figures import bind_theme
from coda_bio_plugin.shared.rendering import caption_html, parse_parameters


def test_caption_uses_caller_namespace_and_escapes_text() -> None:
    assert caption_html(None, namespace="coda-bio-example") == ""
    assert caption_html("<caption>&", namespace="coda-bio-example") == (
        '<p class="coda-bio-example__caption">&lt;caption&gt;&amp;</p>'
    )


def test_common_parameters_are_tool_independent() -> None:
    spec = parse_parameters(
        "bio.example",
        {
            "artifact": "org.example.data",
            "caption": "Author caption",
            "include_table": True,
        },
        supports_table=True,
    )
    assert spec.artifact_type == "org.example.data"
    assert spec.caption == "Author caption"
    assert spec.include_table is True


def test_table_guard_is_plugin_wide_and_defers_to_core() -> None:
    javascript = guard_core_table_js("INITIALIZE_TABLES();")
    assert "data-coda-bio-table-initialized" in javascript
    assert "fastqc" not in javascript
    assert "fastp" not in javascript
    assert "// core.table\\n" in javascript
    assert javascript.count("INITIALIZE_TABLES();") == 1


def test_theme_binding_accepts_tool_supplied_presentation_updates() -> None:
    binding = bind_theme(
        DEFAULT_THEME_PAIR,
        lambda theme: ({"line.color": theme.series[0]},),
        extra_layout=lambda theme: {"shapes[0].fillcolor": theme.colors["primary"]},
    )

    for theme, style in (
        (DEFAULT_THEME_PAIR.light, binding.light),
        (DEFAULT_THEME_PAIR.dark, binding.dark),
    ):
        assert style.traces == ({"line.color": theme.series[0]},)
        assert style.layout["shapes[0].fillcolor"] == theme.colors["primary"]
        assert style.layout["font.family"] == theme.font_body
        assert "xaxis.range" not in style.layout
        assert "yaxis.range" not in style.layout
