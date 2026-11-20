from pathlib import Path

import pytest
from workflow_coda.artifact_store import JsonValue
from workflow_coda.errors import VerificationError

from coda_bio_plugin.fastqc.parser import MODULE_NAMES
from coda_bio_plugin.fastqc.verifier import FASTQC_VERIFIER, verify_fastqc

EXAMPLE = Path("docs/examples/fastqc/fastqc_data.txt")
PARTIAL = (
    b"##FastQC\t0.11.9\n"
    b">>Basic Statistics\tfail\n"
    b"#Measure\tValue\n"
    b"Total Sequences\t0\n"
    b">>END_MODULE\n"
)


def test_example_verifies_independently_of_qc_status() -> None:
    record = FASTQC_VERIFIER.verify(EXAMPLE.read_bytes(), {})
    assert record == {
        "format": "bio.fastqc",
        "status": "ok",
        "fastqc_version": "0.11.9",
        "required_modules_checked": list(MODULE_NAMES),
    }


def test_default_requires_all_standard_modules() -> None:
    with pytest.raises(VerificationError, match="required modules missing"):
        verify_fastqc(PARTIAL, {})


def test_override_accepts_typed_and_flags_transport() -> None:
    typed = verify_fastqc(PARTIAL, {"required_modules": ["Basic Statistics"]})
    flags = verify_fastqc(PARTIAL, {"required_modules": "Basic Statistics"})
    assert typed == flags
    assert typed["status"] == "ok"
    assert typed["required_modules_checked"] == ["Basic Statistics"]


def test_empty_override_allows_no_modules() -> None:
    data = b"##FastQC\t1.0\n"
    assert verify_fastqc(data, {"required_modules": []})["status"] == "ok"
    assert verify_fastqc(data, {"required_modules": ""})["status"] == "ok"


@pytest.mark.parametrize(
    ("criteria", "message"),
    [
        ({"required_module": []}, "did you mean 'required_modules'"),
        ({"required_modules": True}, "must be a list"),
        ({"required_modules": [1]}, "must be a list"),
        ({"required_modules": [""]}, "empty name"),
        ({"required_modules": "Basic Statistics,"}, "empty name"),
        ({"required_modules": ["Unknown"]}, "unknown required module"),
        (
            {"required_modules": ["Basic Statistics", "Basic Statistics"]},
            "names 'Basic Statistics' twice",
        ),
    ],
)
def test_bad_criteria_are_rejected(
    criteria: dict[str, JsonValue], message: str
) -> None:
    with pytest.raises(VerificationError, match=message):
        verify_fastqc(PARTIAL, criteria)


def test_invalid_utf8_is_a_verification_error() -> None:
    with pytest.raises(VerificationError, match="invalid UTF-8"):
        verify_fastqc(b"\xff", {})


def test_present_modules_are_validated_even_when_not_required() -> None:
    data = (
        b"##FastQC\t1\n"
        b">>Per base N content\tpass\n"
        b"#Base\tN-Count\n1\tnan\n"
        b">>END_MODULE\n"
    )
    with pytest.raises(VerificationError, match="must be finite"):
        verify_fastqc(data, {"required_modules": []})
