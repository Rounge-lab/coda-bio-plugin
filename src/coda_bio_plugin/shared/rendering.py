"""Common component parameters and escaped presentation markup."""

import html
from dataclasses import dataclass
from typing import Final

from workflow_coda.components import ComponentParameters, reject_unknown_parameters
from workflow_coda.context import RenderContext
from workflow_coda.text import has_visible_text

_PARAMETERS: Final[frozenset[str]] = frozenset({"artifact", "caption"})
_TABLE_PARAMETERS: Final[frozenset[str]] = _PARAMETERS | {"include_table"}


@dataclass(frozen=True, slots=True)
class RenderSpec:
    """Common artifact, caption, and optional-table parameters."""

    artifact_type: str
    caption: str | None
    include_table: bool


def parse_parameters(
    component_id: str,
    parameters: ComponentParameters,
    *,
    supports_table: bool,
) -> RenderSpec:
    """Validate common parameters before accessing artifact data."""
    accepted = _TABLE_PARAMETERS if supports_table else _PARAMETERS
    reject_unknown_parameters(component_id, parameters, accepted)

    def text_parameter(name: str, *, required: bool) -> str | None:
        if name not in parameters:
            if required:
                raise ValueError(
                    f"{component_id}: parameter {name!r} is required and must "
                    "be a string containing visible text; got missing"
                )
            return None

        value = parameters[name]
        if not isinstance(value, str) or not has_visible_text(value):
            raise ValueError(
                f"{component_id}: parameter {name!r} must be a string "
                f"containing visible text, got {value!r}"
            )
        return value

    artifact_type = text_parameter("artifact", required=True)
    assert artifact_type is not None

    include_table = False
    if supports_table and "include_table" in parameters:
        value = parameters["include_table"]
        if not isinstance(value, bool):
            raise ValueError(
                f"{component_id}: parameter 'include_table' must be a boolean, "
                f"got {value!r}"
            )
        include_table = value

    return RenderSpec(
        artifact_type=artifact_type,
        caption=text_parameter("caption", required=False),
        include_table=include_table,
    )


def caption_html(caption: str | None, *, namespace: str) -> str:
    """Render optional author text using a caller-supplied CSS namespace."""
    if caption is None:
        return ""
    css_class = html.escape(f"{namespace}__caption", quote=True)
    return f'<p class="{css_class}">{html.escape(caption)}</p>'


def disclosure_summary_html(
    context: RenderContext, title: str, *, namespace: str
) -> str:
    """Render an escaped native disclosure label and sanitized core icon."""
    icon = context.icons.load("core-dropdown").markup
    title_class = html.escape(f"{namespace}__disclosure-title", quote=True)
    dropdown_class = html.escape(f"{namespace}__dropdown", quote=True)
    return (
        "<summary>"
        f'<span class="{title_class}">{html.escape(title)}</span>'
        f'<span class="{dropdown_class}">{icon}</span>'
        "</summary>"
    )


def disclosure_html(
    context: RenderContext,
    title: str,
    body: str,
    *,
    namespace: str,
) -> str:
    """Wrap trusted, already-rendered body markup in a native disclosure."""
    css_class = html.escape(f"{namespace}__disclosure", quote=True)
    summary = disclosure_summary_html(context, title, namespace=namespace)
    return f'<details class="{css_class}">{summary}{body}</details>'
