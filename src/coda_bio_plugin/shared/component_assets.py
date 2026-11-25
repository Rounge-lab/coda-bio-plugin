"""Shared presentation and core-table assets for bio components."""

from typing import Final

from .assets import core_table_assets, guard_core_table_js, load_css

BIO_CSS: Final[str] = load_css(
    "coda_bio_plugin",
    "assets/shared.css",
    distribution="coda-bio-plugin",
)

_CORE_TABLE_CSS, _CORE_TABLE_JS = core_table_assets()

BIO_TABLE_CSS: Final[str] = f"{BIO_CSS}\n{_CORE_TABLE_CSS}"
BIO_TABLE_JS: Final[str] = guard_core_table_js(_CORE_TABLE_JS)
