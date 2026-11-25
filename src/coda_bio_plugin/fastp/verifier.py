"""The ``bio.fastp`` artifact verifier.

The default requires summary, filtering results, and read-1 sections before
and after filtering. Mate-2 sections and optional analyses are not required.

``required_sections`` overrides completeness policy with a YAML list or a
comma-separated flags-mode string. An empty list or empty string requires no
sections. Every recognized section present is still parsed and validated.

Verification checks supported structure and completeness, not biological
quality. ``command`` is metadata and cannot be required as a section.
"""

import difflib
import json
from collections.abc import Mapping
from typing import Final, cast

from workflow_coda.artifact_store import JsonValue
from workflow_coda.errors import VerificationError
from workflow_coda.plugins import ArtifactVerifier

from .parser import READ_SECTIONS, FastpParseError, parse_fastp

SECTION_NAMES: Final[tuple[str, ...]] = (
    "summary",
    "filtering_result",
    "duplication",
    "insert_size",
    "adapter_cutting",
    *READ_SECTIONS,
)

DEFAULT_REQUIRED_SECTIONS: Final[tuple[str, ...]] = (
    "summary",
    "filtering_result",
    "read1_before_filtering",
    "read1_after_filtering",
)


def _required_sections(criteria: Mapping[str, JsonValue]) -> list[str]:
    unknown = sorted(key for key in criteria if key != "required_sections")
    if unknown:
        findings = []
        for key in unknown:
            close = difflib.get_close_matches(key, ["required_sections"], n=1)
            hint = f" (did you mean {close[0]!r}?)" if close else ""
            findings.append(f"unknown criterion {key!r}{hint}")
        raise VerificationError(
            "bio.fastp verification: "
            + ", ".join(findings)
            + " — the accepted criterion is 'required_sections'"
        )

    if "required_sections" not in criteria:
        return list(DEFAULT_REQUIRED_SECTIONS)

    value = criteria["required_sections"]
    if isinstance(value, str):
        names = [] if not value.strip() else [part.strip() for part in value.split(",")]
    elif isinstance(value, list) and all(isinstance(item, str) for item in value):
        names = [item for item in value if isinstance(item, str)]
    else:
        raise VerificationError(
            "bio.fastp verification: 'required_sections' must be a list of "
            f"section names or a comma-separated string, got {value!r}"
        )

    seen: set[str] = set()
    for name in names:
        if not name.strip():
            raise VerificationError(
                "bio.fastp verification: 'required_sections' contains an empty name"
            )
        if name not in SECTION_NAMES:
            available = ", ".join(repr(item) for item in SECTION_NAMES)
            raise VerificationError(
                f"bio.fastp verification: unknown required section {name!r} "
                f"— recognized sections are: {available}"
            )
        if name in seen:
            raise VerificationError(
                f"bio.fastp verification: 'required_sections' names {name!r} twice"
            )
        seen.add(name)
    return names


def _reject_constant(value: str) -> JsonValue:
    raise ValueError(f"non-standard numeric constant {value!r}")


def verify_fastp(
    data: bytes, criteria: Mapping[str, JsonValue]
) -> dict[str, JsonValue]:
    """Validate UTF-8 JSON bytes and return a verification record."""
    required = _required_sections(criteria)

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise VerificationError(
            f"bio.fastp verification: invalid UTF-8: {exc}"
        ) from exc

    try:
        payload = cast(
            JsonValue,
            json.loads(text, parse_constant=_reject_constant),
        )
    except ValueError as exc:
        raise VerificationError(f"bio.fastp verification: invalid JSON: {exc}") from exc

    try:
        report = parse_fastp(payload)
    except FastpParseError as exc:
        raise VerificationError(f"bio.fastp verification: {exc}") from exc

    missing = [name for name in required if name not in report.sections]
    if missing:
        raise VerificationError(
            "bio.fastp verification: required sections missing: "
            + ", ".join(repr(name) for name in missing)
        )

    checked: list[JsonValue] = []
    checked.extend(required)
    return {
        "format": "bio.fastp",
        "status": "ok",
        "fastp_version": (
            report.summary.fastp_version if report.summary is not None else None
        ),
        "required_sections_checked": checked,
    }


FASTP_VERIFIER: Final[ArtifactVerifier] = ArtifactVerifier(
    format="bio.fastp",
    verify=verify_fastp,
)
