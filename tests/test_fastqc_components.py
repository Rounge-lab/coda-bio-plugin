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
def test_every_registered_component_renders(tmp_path: Path, item: Any) -> None:
    ctx = context(tmp_path, EXAMPLE.read_text(encoding="utf-8"))
    result = item.render(ctx, PlacementInfo(title="Ignored"), {"artifact": TYPE})
    assert result.status is ComponentStatus.OK
    assert result.html is not None
    assert "Ignored" not in result.html
    if item.id not in {
        "bio.fastqc_overview",
        "bio.fastqc_basic_statistics",
        "bio.fastqc_overrepresented_sequences",
    }:
        assert 'class="coda-figure"' in result.html
        assert 'aria-label="' in result.html
        assert "<summary>Data table</summary>" in result.html


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
    ],
)
def test_parameter_errors_precede_store_access(
    tmp_path: Path, parameters: dict[str, Any]
) -> None:
    ctx = context(tmp_path, "not FastQC", status="failed")
    with pytest.raises(ValueError, match="bio.fastqc_basic_statistics"):
        render(ctx, "bio.fastqc_basic_statistics", parameters)


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


def test_empty_warn_and_fail_are_ok_without_plotly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    text = (
        "##FastQC\t1\n"
        ">>Per base N content\twarn\n>>END_MODULE\n"
        ">>Overrepresented sequences\tfail\n>>END_MODULE\n"
    )
    ctx = context(tmp_path, text)
    monkeypatch.setitem(sys.modules, "plotly", None)
    for id_, label in (
        ("bio.fastqc_per_base_n_content", "Warn"),
        ("bio.fastqc_overrepresented_sequences", "Fail"),
    ):
        outcome = render(ctx, id_, {"artifact": TYPE})
        assert outcome.status is ComponentStatus.OK
        assert outcome.html is not None
        assert label in outcome.html
        assert "This module contains no data rows." in outcome.html
        assert "<table" not in outcome.html


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


def test_stylesheet_has_print_rules() -> None:
    assert ".coda-bio-fastqc__overview" in FASTQC_CSS
    assert "@media print" in FASTQC_CSS
    assert "overflow: visible" in FASTQC_CSS
