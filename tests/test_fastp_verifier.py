import json

import pytest
from workflow_coda.artifact_store import JsonValue
from workflow_coda.errors import VerificationError

from coda_bio_plugin.fastp.verifier import (
    DEFAULT_REQUIRED_SECTIONS,
    FASTP_VERIFIER,
    verify_fastp,
)
from coda_bio_plugin.plugin import get_plugin


def encode(payload: JsonValue) -> bytes:
    return json.dumps(payload).encode("utf-8")


def empty_read() -> dict[str, JsonValue]:
    """Synthetic zero-cycle read section for structural tests."""
    return {
        "total_reads": 0,
        "total_bases": 0,
        "q20_bases": 0,
        "q30_bases": 0,
        "total_cycles": 0,
        "quality_curves": {
            "A": [],
            "T": [],
            "C": [],
            "G": [],
            "mean": [],
        },
        "content_curves": {
            "A": [],
            "T": [],
            "C": [],
            "G": [],
            "N": [],
            "GC": [],
        },
    }


def empty_metrics() -> dict[str, JsonValue]:
    return {
        "total_reads": 0,
        "total_bases": 0,
        "q20_bases": 0,
        "q30_bases": 0,
        "q20_rate": 0,
        "q30_rate": 0,
        "read1_mean_length": 0,
        "gc_content": 0,
    }


def default_payload() -> dict[str, JsonValue]:
    """Synthetic single-end report satisfying default completeness."""
    return {
        "summary": {
            "fastp_version": "1.0.0",
            "before_filtering": empty_metrics(),
            "after_filtering": empty_metrics(),
        },
        "filtering_result": {
            "passed_filter_reads": 0,
            "low_quality_reads": 0,
            "too_many_N_reads": 0,
            "too_short_reads": 0,
        },
        "read1_before_filtering": empty_read(),
        "read1_after_filtering": empty_read(),
    }


def test_default_single_end_report_verifies() -> None:
    record = FASTP_VERIFIER.verify(encode(default_payload()), {})
    assert record == {
        "format": "bio.fastp",
        "status": "ok",
        "fastp_version": "1.0.0",
        "required_sections_checked": list(DEFAULT_REQUIRED_SECTIONS),
    }


def test_paired_report_verifies_without_changing_default_requirements() -> None:
    payload = default_payload()
    payload["read2_before_filtering"] = empty_read()
    payload["read2_after_filtering"] = empty_read()

    record = verify_fastp(encode(payload), {})
    assert record["required_sections_checked"] == list(DEFAULT_REQUIRED_SECTIONS)


def test_default_requires_core_sections() -> None:
    with pytest.raises(VerificationError, match="required sections missing"):
        verify_fastp(b"{}", {})


def test_missing_sections_are_reported_in_requirement_order() -> None:
    with pytest.raises(VerificationError) as error:
        verify_fastp(
            b"{}",
            {"required_sections": ["read2_after_filtering", "insert_size"]},
        )
    assert str(error.value) == (
        "bio.fastp verification: required sections missing: "
        "'read2_after_filtering', 'insert_size'"
    )


def test_override_accepts_typed_and_flags_transport() -> None:
    data = encode({"duplication": {"rate": 0.99}})
    typed = verify_fastp(data, {"required_sections": ["duplication"]})
    flags = verify_fastp(data, {"required_sections": " duplication "})

    assert typed == flags
    assert typed == {
        "format": "bio.fastp",
        "status": "ok",
        "fastp_version": None,
        "required_sections_checked": ["duplication"],
    }


def test_empty_override_allows_no_sections() -> None:
    values: list[JsonValue] = [[], "", "   "]
    for value in values:
        record = verify_fastp(b"{}", {"required_sections": value})
        assert record["status"] == "ok"
        assert record["required_sections_checked"] == []


@pytest.mark.parametrize(
    ("criteria", "message"),
    [
        ({"required_section": []}, "did you mean 'required_sections'"),
        ({"other": []}, "unknown criterion"),
        ({"required_sections": True}, "must be a list"),
        ({"required_sections": None}, "must be a list"),
        ({"required_sections": [1]}, "must be a list"),
        ({"required_sections": [""]}, "empty name"),
        ({"required_sections": ["   "]}, "empty name"),
        ({"required_sections": "summary,"}, "empty name"),
        ({"required_sections": ["Unknown"]}, "unknown required section"),
        ({"required_sections": ["command"]}, "unknown required section"),
        ({"required_sections": ["Summary"]}, "unknown required section"),
        (
            {"required_sections": ["summary", "summary"]},
            "names 'summary' twice",
        ),
        (
            {"required_sections": "summary, summary"},
            "names 'summary' twice",
        ),
    ],
)
def test_bad_criteria_are_rejected(
    criteria: dict[str, JsonValue], message: str
) -> None:
    with pytest.raises(VerificationError, match=message):
        verify_fastp(b"{}", criteria)


def test_criteria_are_checked_before_artifact_decoding() -> None:
    with pytest.raises(VerificationError, match="unknown criterion"):
        verify_fastp(b"\xff", {"other": []})


def test_invalid_utf8_is_a_verification_error() -> None:
    with pytest.raises(VerificationError, match="invalid UTF-8"):
        verify_fastp(b"\xff", {})


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"{",
        b'{"summary":}',
        b"{} trailing",
        b'{"future": NaN}',
        b'{"future": Infinity}',
        b'{"future": -Infinity}',
    ],
)
def test_invalid_json_is_a_verification_error(data: bytes) -> None:
    with pytest.raises(VerificationError, match="invalid JSON"):
        verify_fastp(data, {"required_sections": []})


@pytest.mark.parametrize("data", [b"null", b"[]", b"42", b'"text"'])
def test_non_object_json_is_a_verification_error(data: bytes) -> None:
    with pytest.raises(VerificationError, match="expected an object"):
        verify_fastp(data, {"required_sections": []})


def test_present_sections_are_validated_even_when_not_required() -> None:
    data = encode({"duplication": {"rate": 1.1}})
    with pytest.raises(VerificationError, match="between 0 and 1"):
        verify_fastp(data, {"required_sections": []})


def test_present_null_is_not_a_missing_section() -> None:
    with pytest.raises(VerificationError, match="summary: expected an object"):
        verify_fastp(b'{"summary": null}', {"required_sections": []})


def test_unknown_sections_do_not_invalidate_a_report() -> None:
    payload = default_payload()
    payload["future_section"] = {"uninterpreted": [1, 2]}
    assert verify_fastp(encode(payload), {})["status"] == "ok"


def test_plugin_registers_fastp_and_preserves_fastqc_verifier() -> None:
    formats = {verifier.format for verifier in get_plugin().artifact_verifiers}
    assert {"bio.fastqc", "bio.fastp"} <= formats
