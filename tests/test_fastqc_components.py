"""FastQC components exercised through their registered roster and real stores."""

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from workflow_coda.artifact_store import ArtifactStore
from workflow_coda.components import ComponentChrome, ComponentStatus, PlacementInfo
from workflow_coda.context import RenderContext
from workflow_coda.errors import ArtifactReadError
from workflow_coda.icons import IconLibrary, IconSource
from workflow_coda.manifest import MANIFEST_SCHEMA_VERSION

from coda_bio_plugin.fastqc.components import FASTQC_CSS
from coda_bio_plugin.fastqc.parser import MODULE_NAMES
from coda_bio_plugin.plugin import get_plugin

TYPE = "org.example.fastqc"
EXAMPLE = Path("docs/examples/fastqc/fastqc_data.txt")


def context(
    tmp_path: Path,
    text: str,
    *,
    fmt: str = "bio.fastqc",
    status: str = "complete",
    icons: bool = True,
) -> RenderContext:
    (tmp_path / "fastqc.txt").write_text(text, encoding="utf-8")
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "producer": {"name": "fixture", "version": "1"},
        "artifacts": [
            {
                "id": "fastqc",
                "type": TYPE,
                "schema_version": "1.0",
                "path": "fastqc.txt",
                "format": fmt,
                "status": status,
            }
        ],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    sources = (IconSource.for_plugin("core", "workflow_coda.core"),) if icons else ()
    return RenderContext(
        store=ArtifactStore.from_manifest_file(path), icons=IconLibrary(sources)
    )


def component(id_: str) -> Any:
    return next(item for item in get_plugin().components if item.id == id_)


def render(ctx: RenderContext, id_: str, parameters: dict[str, Any]) -> Any:
    return component(id_).render(ctx, PlacementInfo(title="Ignored"), parameters)


def test_registration() -> None:
    first = get_plugin()
    second = get_plugin()
    assert first is not second
    assert len(first.components) == 11
    assert first.components[0].id == "bio.fastqc_overview"
    assert [item.title for item in first.components[1:]] == list(MODULE_NAMES)
    assert all(item.chrome is ComponentChrome.CARD for item in first.components)
    assert all(item.css == FASTQC_CSS and item.js is None for item in first.components)
    assert [item.format for item in first.artifact_verifiers] == ["bio.fastqc"]
    assert first.metadata.icons_package is None


@pytest.mark.parametrize("item", get_plugin().components, ids=lambda item: item.id)
def test_every_registered_component_renders_by_default(
    tmp_path: Path, item: Any
) -> None:
    ctx = context(tmp_path, EXAMPLE.read_text(encoding="utf-8"))
    result = item.render(ctx, PlacementInfo(title="Ignored"), {"artifact": TYPE})
    assert result.status is ComponentStatus.OK
    assert result.html is not None
    assert "Ignored" not in result.html
    assert "<summary>Data table</summary>" not in result.html
    if item.id == "bio.fastqc_basic_statistics":
        assert "<table" in result.html
        assert "VC1_1.fastq.gz" in result.html
    else:
        assert "<table" not in result.html
    if item.id not in {
        "bio.fastqc_overview",
        "bio.fastqc_basic_statistics",
        "bio.fastqc_overrepresented_sequences",
    }:
        assert 'class="coda-figure"' in result.html
        assert 'aria-label="' in result.html


@pytest.mark.parametrize(
    ("id_", "text"),
    [
        (
            "bio.fastqc_per_base_n_content",
            "##FastQC\t1\n"
            ">>Per base N content\tpass\n"
            "#Base\tN-Count\n"
            "1\t0\n"
            ">>END_MODULE\n",
        ),
        (
            "bio.fastqc_overrepresented_sequences",
            "##FastQC\t1\n"
            ">>Overrepresented sequences\tpass\n"
            "#Sequence\tCount\tPercentage\tPossible Source\n"
            "ACGT\t3\t1.5\tadapter\n"
            ">>END_MODULE\n",
        ),
    ],
)
@pytest.mark.parametrize("include_table", [False, True], ids=["disabled", "enabled"])
def test_optional_table_for_chart_and_table_components(
    tmp_path: Path,
    id_: str,
    text: str,
    include_table: bool,
) -> None:
    ctx = context(tmp_path, text)
    parameters: dict[str, Any] = {"artifact": TYPE}
    if include_table:
        parameters["include_table"] = True
    outcome = render(ctx, id_, parameters)
    assert outcome.status is ComponentStatus.OK
    assert outcome.html is not None
    if id_ == "bio.fastqc_per_base_n_content":
        assert 'class="coda-figure"' in outcome.html
    if include_table:
        if id_ == "bio.fastqc_per_base_n_content":
            assert "<summary>Data table</summary>" in outcome.html
        assert "<table" in outcome.html
        assert "ACGT" in outcome.html or id_ != "bio.fastqc_overrepresented_sequences"
    else:
        assert "<table" not in outcome.html
        assert "<summary>Data table</summary>" not in outcome.html
        assert "ACGT" not in outcome.html


@pytest.mark.parametrize(
    "parameters",
    [
        {},
        {"artifact": None},
        {"artifact": 3},
        {"artifact": "  "},
        {"artifact": TYPE, "caption": None},
        {"artifact": TYPE, "caption": 3},
        {"artifact": TYPE, "caption": "  "},
        {"artifact": TYPE, "artifct": "x"},
        {"artifact": TYPE, "title": "misplaced"},
        {"artifact": TYPE, "include_table": None},
        {"artifact": TYPE, "include_table": "true"},
        {"artifact": TYPE, "include_table": 1},
    ],
)
def test_parameter_errors_precede_store_access(
    tmp_path: Path, parameters: dict[str, Any]
) -> None:
    ctx = context(tmp_path, "not FastQC", status="failed")
    with pytest.raises(ValueError, match="bio.fastqc_overrepresented_sequences"):
        render(ctx, "bio.fastqc_overrepresented_sequences", parameters)


def test_basic_statistics_rejects_include_table_before_store_access(
    tmp_path: Path,
) -> None:
    ctx = context(tmp_path, "not FastQC", status="failed")
    with pytest.raises(ValueError, match="bio.fastqc_basic_statistics"):
        render(
            ctx,
            "bio.fastqc_basic_statistics",
            {"artifact": TYPE, "include_table": False},
        )


def test_overview_rejects_include_table_before_store_access(tmp_path: Path) -> None:
    ctx = context(tmp_path, "not FastQC", status="failed")
    with pytest.raises(ValueError, match="bio.fastqc_overview"):
        render(ctx, "bio.fastqc_overview", {"artifact": TYPE, "include_table": True})


def test_format_and_parse_failures(tmp_path: Path) -> None:
    ctx = context(tmp_path, "bad", fmt="txt")
    with pytest.raises(ValueError, match="expected 'bio.fastqc'"):
        render(ctx, "bio.fastqc_basic_statistics", {"artifact": TYPE})
    ctx = context(tmp_path, "bad")
    with pytest.raises(ArtifactReadError, match="fastqc") as caught:
        render(ctx, "bio.fastqc_basic_statistics", {"artifact": TYPE})
    assert caught.value.__cause__ is not None


def test_unavailable_and_missing_modules(tmp_path: Path) -> None:
    ctx = context(tmp_path, "bad", status="failed", icons=False)
    outcome = render(ctx, "bio.fastqc_overview", {"artifact": TYPE})
    assert outcome.status is ComponentStatus.UNAVAILABLE
    ctx = context(tmp_path, "##FastQC\t1\n")
    outcome = render(ctx, "bio.fastqc_basic_statistics", {"artifact": TYPE})
    assert outcome.status is ComponentStatus.UNAVAILABLE
    assert outcome.message is not None
    assert "carries no module 'Basic Statistics'" in outcome.message
    outcome = render(ctx, "bio.fastqc_overview", {"artifact": "org.example.absent"})
    assert outcome.status is ComponentStatus.UNAVAILABLE


@pytest.mark.parametrize(
    ("body", "include_table", "has_header", "has_metadata"),
    [
        ("", False, False, False),
        ("", True, False, False),
        ("#Base\tN-Count\n", False, True, False),
        ("#Base\tN-Count\n", True, True, False),
        (
            "#Total Deduplicated Percentage\t62.5\n",
            False,
            False,
            True,
        ),
        (
            "#Total Deduplicated Percentage\t62.5\n"
            "#Duplication Level\tPercentage of deduplicated\tPercentage of total\n",
            True,
            True,
            True,
        ),
    ],
)
def test_empty_modules_table_options_and_no_plotly_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    body: str,
    include_table: bool,
    has_header: bool,
    has_metadata: bool,
) -> None:
    if has_metadata:
        module_name = "Sequence Duplication Levels"
        component_id = "bio.fastqc_sequence_duplication_levels"
    else:
        module_name = "Per base N content"
        component_id = "bio.fastqc_per_base_n_content"
    text = f"##FastQC\t1\n>>{module_name}\twarn\n{body}>>END_MODULE\n"
    ctx = context(tmp_path, text)
    monkeypatch.setitem(sys.modules, "plotly", None)
    parameters: dict[str, Any] = {"artifact": TYPE}
    if include_table:
        parameters["include_table"] = True

    outcome = render(ctx, component_id, parameters)
    assert outcome.status is ComponentStatus.OK
    assert outcome.html is not None
    assert "Warn" in outcome.html
    assert "This module contains no data rows." in outcome.html
    assert ("<table" in outcome.html) is (include_table and has_header)
    assert ("Total Deduplicated Percentage" in outcome.html) is has_metadata
    assert ("<th scope=" in outcome.html) is (include_table and has_header)


@pytest.mark.parametrize(
    ("body", "has_table_header"),
    [
        ("#Measure\tValue\n", True),
        ("", False),
    ],
)
def test_basic_statistics_always_shows_empty_notice_and_available_header(
    tmp_path: Path,
    body: str,
    has_table_header: bool,
) -> None:
    text = f"##FastQC\t1\n>>Basic Statistics\twarn\n{body}>>END_MODULE\n"
    ctx = context(tmp_path, text)

    outcome = render(ctx, "bio.fastqc_basic_statistics", {"artifact": TYPE})

    assert outcome.status is ComponentStatus.OK
    assert outcome.html is not None
    assert "This module contains no data rows." in outcome.html
    assert ("<table" in outcome.html) is has_table_header
    assert ("<th scope=" in outcome.html) is has_table_header
    if has_table_header:
        assert "Measure" in outcome.html
        assert "Value" in outcome.html


def test_overview_counts_order_and_additional_modules(tmp_path: Path) -> None:
    text = (
        "##FastQC\t1<&\n"
        ">>Basic Statistics\tpass\n>>END_MODULE\n"
        ">>Per base N content\twarn\n>>END_MODULE\n"
        ">>Adapter Content\tfail\n>>END_MODULE\n"
        ">>Extra <module>\twarn\nopaque\n>>END_MODULE\n"
    )
    ctx = context(tmp_path, text)
    outcome = render(ctx, "bio.fastqc_overview", {"artifact": TYPE})
    assert outcome.status is ComponentStatus.OK
    assert outcome.html is not None
    page = outcome.html
    assert "1&lt;&amp;" in page
    assert "Pass: 1; Warn: 1; Fail: 1; Unavailable: 7" in page
    assert page.count('class="coda-icon"') == 3
    assert page.index("Basic Statistics") < page.index("Per base sequence quality")
    assert page.index("Per base N content") < page.index("Adapter Content")
    assert "<summary>Additional modules</summary>" in page
    assert "Extra &lt;module&gt;: Warn" in page
    for icon in ("core-check", "core-info", "core-warning"):
        assert ctx.icons.load(icon).markup in page


@pytest.mark.parametrize(
    ("status", "token", "label"),
    [
        ("pass", "success", "Pass"),
        ("warn", "warning", "Warn"),
        ("fail", "danger", "Fail"),
    ],
)
def test_status_borders_keep_neutral_border_and_color_left_edge(
    tmp_path: Path,
    status: str,
    token: str,
    label: str,
) -> None:
    text = (
        "##FastQC\t1\n"
        f">>Basic Statistics\t{status}\n"
        ">>END_MODULE\n"
    )
    ctx = context(tmp_path, text)
    expected_color = ctx.theme.colors[token]
    expected_left_border = f"border-left-color: {expected_color};"

    badge = render(ctx, "bio.fastqc_basic_statistics", {"artifact": TYPE})
    assert badge.html is not None
    assert (
        '<span class="coda-bio-fastqc__status" '
        f'style="{expected_left_border}">{label}</span>'
    ) in badge.html

    overview = render(ctx, "bio.fastqc_overview", {"artifact": TYPE})
    assert overview.html is not None
    assert (
        '<li class="coda-bio-fastqc__overview-item" '
        f'style="{expected_left_border}">'
    ) in overview.html
    assert (
        '<span class="coda-bio-fastqc__icon" '
        f'style="color: {expected_color};">'
    ) in overview.html

    unavailable_item = overview.html.split(
        '<li class="coda-bio-fastqc__overview-item '
        'coda-bio-fastqc__overview-item--unavailable">',
        maxsplit=1,
    )[1].split("</li>", maxsplit=1)[0]
    assert "style=" not in unavailable_item


def test_escaped_complete_table_and_caption(tmp_path: Path) -> None:
    text = (
        "##FastQC\t1\n"
        ">>Basic Statistics\tpass\n"
        "#Measure\tValue\tExtra <header>\n"
        "Filename\t<a&b>\tkeep & this\n"
        ">>END_MODULE\n"
    )
    ctx = context(tmp_path, text)
    outcome = render(
        ctx,
        "bio.fastqc_basic_statistics",
        {"artifact": TYPE, "caption": "<caption>&"},
    )
    assert outcome.html is not None
    assert "Extra &lt;header&gt;" in outcome.html
    assert "&lt;a&amp;b&gt;" in outcome.html
    assert "keep &amp; this" in outcome.html
    assert "&lt;caption&gt;&amp;" in outcome.html


def test_chart_disclosure_contains_complete_escaped_table(tmp_path: Path) -> None:
    text = (
        "##FastQC\t1\n"
        ">>Per base N content\tpass\n"
        "#Base\tN-Count\tExtra <header>\n"
        "1\t0\t<a&b>\n"
        ">>END_MODULE\n"
    )
    ctx = context(tmp_path, text)
    outcome = render(
        ctx,
        "bio.fastqc_per_base_n_content",
        {"artifact": TYPE, "include_table": True},
    )
    assert outcome.html is not None
    assert "<summary>Data table</summary>" in outcome.html
    assert "Extra &lt;header&gt;" in outcome.html
    assert "&lt;a&amp;b&gt;" in outcome.html


def test_stylesheet_has_print_rules() -> None:
    assert ".coda-bio-fastqc__overview" in FASTQC_CSS
    assert "border: 1px solid var(--coda-border);" in FASTQC_CSS
    assert "border-left-width: 4px;" in FASTQC_CSS
    assert "@media print" in FASTQC_CSS
    assert "overflow: visible" in FASTQC_CSS
