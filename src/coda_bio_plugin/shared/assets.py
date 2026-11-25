"""Packaged assets and version-coupled core-table integration."""

from importlib import resources

from workflow_coda.core.plugin import _TABLE
from workflow_coda.errors import PluginAssetError


def load_css(package: str, path: str, *, distribution: str) -> str:
    """Read packaged UTF-8 CSS with an actionable installation error."""
    try:
        return resources.files(package).joinpath(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise PluginAssetError(
            f"{distribution} asset {path!r} is missing or unreadable "
            f"— reinstall {distribution}"
        ) from exc


def core_table_assets() -> tuple[str, str]:
    """Return the installed core table's declared CSS and JavaScript.

    This private integration must be tested when workflow-coda is upgraded.
    """
    if _TABLE.css is None or _TABLE.js is None:
        raise PluginAssetError(
            "workflow-coda core.table must declare CSS and JavaScript "
            "for coda-bio-plugin table integration"
        )
    return _TABLE.css, _TABLE.js


def guard_core_table_js(core_js: str) -> str:
    """Initialize core tables once across all bio component contributions.

    A core.table contribution takes precedence, independent of contribution
    order. Otherwise the first bio contribution initializes all tables.
    """
    return (
        "(function () {\n"
        '  "use strict";\n'
        '  document.documentElement.classList.add("coda-js");\n'
        "  var source = document.currentScript\n"
        "    ? document.currentScript.textContent\n"
        '    : "";\n'
        '  if (source.indexOf("// core.table\\n") !== -1) {\n'
        "    return;\n"
        "  }\n"
        '  var marker = "data-coda-bio-table-initialized";\n'
        "  if (document.documentElement.hasAttribute(marker)) {\n"
        "    return;\n"
        "  }\n"
        '  document.documentElement.setAttribute(marker, "true");\n'
        f"{core_js}\n"
        "}());"
    )
