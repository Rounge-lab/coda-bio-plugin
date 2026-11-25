"""fastp parser tests.

Single-end and empty-result cases are synthetic structural variants,
not reports produced by fastp.
"""

import re
from collections.abc import Mapping

import pytest
from workflow_coda.manifest import JsonValue

from coda_bio_plugin.fastp.parser import FastpParseError, parse_fastp


def summary_metrics(*, paired: bool = True) -> dict[str, JsonValue]:
    metrics: dict[str, JsonValue] = {
        "total_reads": 20,
        "total_bases": 60,
        "q20_bases": 57,
        "q30_bases": 54,
        "q20_rate": 0.95,
        "q30_rate": 0.9,
        "read1_mean_length": 3,
        "gc_content": 0.5,
    }
    if paired:
        metrics["read2_mean_length"] = 3
    return metrics


def read_section(*, cycles: int = 3, reads: int = 10) -> dict[str, JsonValue]:
    """Synthetic supported read section, not a fastp-produced fixture."""
    quality: dict[str, JsonValue] = {}
    for name in ("A", "T", "C", "G", "mean"):
        values: list[JsonValue] = [35.0] * cycles
        quality[name] = values

    content: dict[str, JsonValue] = {}
    for name, fraction in (
        ("A", 0.25),
        ("T", 0.25),
        ("C", 0.25),
        ("G", 0.25),
        ("N", 0.0),
        ("GC", 0.5),
    ):
        fractions: list[JsonValue] = [fraction] * cycles
        content[name] = fractions

    return {
        "total_reads": reads,
        "total_bases": reads * cycles,
        "q20_bases": reads * cycles,
        "q30_bases": reads * cycles,
        "q40_bases": 0,
        "total_cycles": cycles,
        "quality_curves": quality,
        "content_curves": content,
        "kmer_count": {"AAAAA": 0},
        "overrepresented_sequences": {},
    }


def example_payload(*, paired: bool = True) -> dict[str, JsonValue]:
    """Compact synthetic report for unit tests."""
    payload: dict[str, JsonValue] = {
        "summary": {
            "fastp_version": "1.0.0",
            "sequencing": "paired end" if paired else "single end",
            "before_filtering": summary_metrics(paired=paired),
            "after_filtering": summary_metrics(paired=paired),
        },
        "filtering_result": {
            "passed_filter_reads": 20,
            "low_quality_reads": 0,
            "too_many_N_reads": 0,
            "too_short_reads": 0,
            "too_long_reads": 0,
        },
        "duplication": {"rate": 0.1},
        "adapter_cutting": {
            "adapter_trimmed_reads": 2,
            "adapter_trimmed_bases": 4,
            "read1_adapter_sequence": "ACGT",
            "read1_adapter_counts": {"AC": 1, "others": 1},
        },
        "read1_before_filtering": read_section(),
        "read1_after_filtering": read_section(),
        "command": "fastp -i reads.fastq.gz",
    }
    if paired:
        payload["read2_before_filtering"] = read_section()
        payload["read2_after_filtering"] = read_section()
        payload["insert_size"] = {
            "peak": 2,
            "unknown": 1,
            "histogram": [0, 1, 4, 2],
        }
    return payload


def object_at(source: Mapping[str, JsonValue], *keys: str) -> dict[str, JsonValue]:
    current = source
    for key in keys:
        value = current[key]
        assert isinstance(value, dict)
        current = value
    assert isinstance(current, dict)
    return current


def test_paired_report_preserves_supported_values() -> None:
    report = parse_fastp(example_payload())

    assert report.summary is not None
    assert report.summary.fastp_version == "1.0.0"
    assert report.summary.before_filtering.total_reads == 20
    assert report.summary.after_filtering.q30_rate == 0.9
    assert report.summary.before_filtering.read2_mean_length == 3

    assert report.filtering_result is not None
    assert report.filtering_result.too_many_n_reads == 0

    assert report.read1_before_filtering is not None
    assert report.read1_before_filtering.total_cycles == 3
    assert report.read1_before_filtering.quality_curves["mean"] == (
        35.0,
        35.0,
        35.0,
    )
    assert report.read2_after_filtering is not None

    assert report.duplication is not None
    assert report.duplication.rate == 0.1

    assert report.insert_size is not None
    assert report.insert_size.histogram == (0, 1, 4, 2)

    assert report.adapter_cutting is not None
    assert report.adapter_cutting.read1_adapter_counts == {"AC": 1, "others": 1}
    assert report.command == "fastp -i reads.fastq.gz"


def test_single_end_report_does_not_require_mate_fields() -> None:
    report = parse_fastp(example_payload(paired=False))

    assert report.read1_before_filtering is not None
    assert report.read2_before_filtering is None
    assert report.read2_after_filtering is None
    assert report.insert_size is None
    assert report.summary is not None
    assert report.summary.before_filtering.read2_mean_length is None
    assert report.adapter_cutting is not None
    assert report.adapter_cutting.read2_adapter_sequence is None
    assert report.adapter_cutting.read2_adapter_counts is None


def test_empty_read_section() -> None:
    report = parse_fastp({"read1_after_filtering": read_section(cycles=0, reads=0)})

    assert report.read1_after_filtering is not None
    assert report.read1_after_filtering.total_reads == 0
    assert report.read1_after_filtering.quality_curves["mean"] == ()
    assert report.read1_after_filtering.content_curves["GC"] == ()


def test_sections_may_have_different_cycle_counts() -> None:
    report = parse_fastp(
        {
            "read1_before_filtering": read_section(cycles=3),
            "read1_after_filtering": read_section(cycles=2),
            "read2_after_filtering": read_section(cycles=1),
        }
    )

    assert report.read1_before_filtering is not None
    assert report.read1_before_filtering.total_cycles == 3
    assert report.read1_after_filtering is not None
    assert report.read1_after_filtering.total_cycles == 2
    assert report.read2_after_filtering is not None
    assert report.read2_after_filtering.total_cycles == 1


def test_missing_sections_are_not_completeness_errors() -> None:
    report = parse_fastp({})

    assert report.sections == frozenset()
    assert report.summary is None
    assert report.filtering_result is None


def test_unknown_fields_do_not_invalidate_supported_sections() -> None:
    payload = example_payload()
    payload["future_section"] = {"uninterpreted": [1, 2]}
    object_at(payload, "summary")["future_metric"] = 42

    report = parse_fastp(payload)

    assert report.summary is not None
    assert "future_section" not in report.sections


def test_optional_fields_may_be_absent() -> None:
    payload = example_payload()
    object_at(payload, "filtering_result").pop("too_long_reads")
    read = object_at(payload, "read1_before_filtering")
    for key in ("q40_bases", "kmer_count", "overrepresented_sequences"):
        read.pop(key)

    report = parse_fastp(payload)

    assert report.filtering_result is not None
    assert report.filtering_result.too_long_reads is None
    assert report.read1_before_filtering is not None
    assert report.read1_before_filtering.q40_bases is None
    assert report.read1_before_filtering.kmer_count is None


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (None, "expected an object"),
        ([], "expected an object"),
        ("fastp", "expected an object"),
        (42, "expected an object"),
        (True, "expected an object"),
        ({"summary": None}, "summary: expected an object"),
        ({"summary": {}}, "before_filtering: required field is missing"),
        ({"filtering_result": {}}, "passed_filter_reads: required field"),
        ({"duplication": {"rate": 1.1}}, "between 0 and 1"),
        ({"duplication": {"rate": True}}, "finite number"),
        ({"duplication": {"rate": float("nan")}}, "finite number"),
        ({"duplication": {"rate": float("inf")}}, "finite number"),
        ({"command": 42}, "command: expected a string"),
        (
            {"insert_size": {"peak": 2, "unknown": 0, "histogram": "bad"}},
            "histogram: expected an array",
        ),
        (
            {"insert_size": {"peak": 2, "unknown": 0, "histogram": [0, -1]}},
            re.escape("histogram[1]: expected a non-negative integer"),
        ),
    ],
)
def test_invalid_artifacts_teach(payload: JsonValue, message: str) -> None:
    with pytest.raises(FastpParseError, match=message):
        parse_fastp(payload)


@pytest.mark.parametrize("value", [True, -1, 1.5, "10", None])
def test_invalid_read_counts_teach(value: JsonValue) -> None:
    read = read_section()
    read["total_reads"] = value

    with pytest.raises(
        FastpParseError,
        match="read1_before_filtering.total_reads: expected a non-negative integer",
    ):
        parse_fastp({"read1_before_filtering": read})


@pytest.mark.parametrize("value", [True, -0.1, 1.1, float("nan"), float("inf")])
def test_invalid_summary_fractions_teach(value: JsonValue) -> None:
    payload = example_payload()
    object_at(payload, "summary", "before_filtering")["q30_rate"] = value

    with pytest.raises(FastpParseError, match="summary.before_filtering.q30_rate"):
        parse_fastp(payload)


@pytest.mark.parametrize("value", [True, -1, float("nan"), float("inf")])
def test_invalid_quality_reports_element_path(value: JsonValue) -> None:
    read = read_section()
    object_at(read, "quality_curves")["mean"] = [35, value, 35]

    with pytest.raises(
        FastpParseError,
        match=re.escape("read1_before_filtering.quality_curves.mean[1]"),
    ):
        parse_fastp({"read1_before_filtering": read})


def test_quality_has_no_arbitrary_upper_limit() -> None:
    read = read_section()
    object_at(read, "quality_curves")["mean"] = [45, 45, 45]

    report = parse_fastp({"read1_before_filtering": read})

    assert report.read1_before_filtering is not None
    assert report.read1_before_filtering.quality_curves["mean"] == (45, 45, 45)


@pytest.mark.parametrize("group", ["quality_curves", "content_curves"])
def test_curve_lengths_must_match_total_cycles(group: str) -> None:
    read = read_section()
    object_at(read, group)["A"] = [0.25]

    with pytest.raises(FastpParseError, match="expected 3 values.*got 1"):
        parse_fastp({"read1_before_filtering": read})


def test_content_curve_values_are_fractions() -> None:
    read = read_section()
    object_at(read, "content_curves")["GC"] = [0.5, 1.5, 0.5]

    with pytest.raises(
        FastpParseError,
        match=re.escape("content_curves.GC[1]: expected a fraction"),
    ):
        parse_fastp({"read1_before_filtering": read})


def test_present_read_requires_essential_fields() -> None:
    read = read_section()
    read.pop("quality_curves")

    with pytest.raises(
        FastpParseError,
        match="quality_curves: required field is missing",
    ):
        parse_fastp({"read1_before_filtering": read})


def test_adapter_count_labels_are_unrestricted_but_counts_are_validated() -> None:
    payload = example_payload()
    counts = object_at(payload, "adapter_cutting", "read1_adapter_counts")
    counts["others"] = True

    with pytest.raises(
        FastpParseError,
        match=re.escape("adapter_cutting.read1_adapter_counts['others']"),
    ):
        parse_fastp(payload)


def test_kmer_counts_are_validated() -> None:
    read = read_section()
    read["kmer_count"] = {"AAAAA": -1}

    with pytest.raises(
        FastpParseError,
        match=re.escape("kmer_count['AAAAA']"),
    ):
        parse_fastp({"read1_before_filtering": read})


def test_overrepresented_sequences_requires_an_object() -> None:
    read = read_section()
    read["overrepresented_sequences"] = []

    with pytest.raises(FastpParseError, match="overrepresented_sequences"):
        parse_fastp({"read1_before_filtering": read})


def test_parsed_values_are_detached_from_input() -> None:
    read = read_section()
    report = parse_fastp({"read1_before_filtering": read})
    object_at(read, "quality_curves")["mean"] = [0, 0, 0]

    assert report.read1_before_filtering is not None
    assert report.read1_before_filtering.quality_curves["mean"] == (35, 35, 35)
