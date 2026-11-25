"""The ``bio.fastqc`` artifact verifier.

The default requires the ten standard modules. ``required_modules`` overrides
that policy with a YAML list or a comma-separated flags-mode string. An empty
list, or an empty flags-mode string, requires no modules. Parsing and validation
still apply to every recognized module that is present.

Verification describes the artifact's format and completeness, not the QC
outcome: FastQC's ``warn`` and ``fail`` module statuses are valid data.
"""

import difflib
from collections.abc import Mapping
from typing import Final

from workflow_coda.artifact_store import JsonValue
from workflow_coda.errors import VerificationError
from workflow_coda.plugins import ArtifactVerifier

from .parser import MODULE_NAMES, FastqcParseError, parse_fastqc


def _required_modules(criteria: Mapping[str, JsonValue]) -> list[str]:
    unknown = sorted(key for key in criteria if key != "required_modules")
    if unknown:
        findings = []
        for key in unknown:
            close = difflib.get_close_matches(key, ["required_modules"], n=1)
            hint = f" (did you mean {close[0]!r}?)" if close else ""
            findings.append(f"unknown criterion {key!r}{hint}")
        raise VerificationError(
            "bio.fastqc verification: "
            + ", ".join(findings)
            + " — the accepted criterion is 'required_modules'"
        )

    if "required_modules" not in criteria:
        return list(MODULE_NAMES)

    value = criteria["required_modules"]
    if isinstance(value, str):
        names = [] if not value.strip() else [part.strip() for part in value.split(",")]
    elif isinstance(value, list) and all(isinstance(item, str) for item in value):
        names = [item for item in value if isinstance(item, str)]
    else:
        raise VerificationError(
            "bio.fastqc verification: 'required_modules' must be a list of "
            f"module names or a comma-separated string, got {value!r}"
        )

    seen: set[str] = set()
    for name in names:
        if not name.strip():
            raise VerificationError(
                "bio.fastqc verification: 'required_modules' contains an empty name"
            )
        if name not in MODULE_NAMES:
            available = ", ".join(repr(item) for item in MODULE_NAMES)
            raise VerificationError(
                f"bio.fastqc verification: unknown required module {name!r} "
                f"— recognized modules are: {available}"
            )
        if name in seen:
            raise VerificationError(
                f"bio.fastqc verification: 'required_modules' names {name!r} twice"
            )
        seen.add(name)
    return names


def verify_fastqc(
    data: bytes, criteria: Mapping[str, JsonValue]
) -> dict[str, JsonValue]:
    """Validate bytes and return a JSON-compatible verification record."""
    required = _required_modules(criteria)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise VerificationError(
            f"bio.fastqc verification: invalid UTF-8: {exc}"
        ) from exc
    try:
        report = parse_fastqc(text)
    except FastqcParseError as exc:
        raise VerificationError(f"bio.fastqc verification: {exc}") from exc

    present = {module.name for module in report.modules}
    missing = [name for name in required if name not in present]
    if missing:
        raise VerificationError(
            "bio.fastqc verification: required modules missing: "
            + ", ".join(repr(name) for name in missing)
        )

    checked: list[JsonValue] = []
    checked.extend(required)
    return {
        "format": "bio.fastqc",
        "status": "ok",
        "fastqc_version": report.version,
        "required_modules_checked": checked,
    }


FASTQC_VERIFIER: Final[ArtifactVerifier] = ArtifactVerifier(
    format="bio.fastqc",
    verify=verify_fastqc,
)
