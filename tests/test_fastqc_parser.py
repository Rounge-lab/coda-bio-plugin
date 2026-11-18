from pathlib import Path

import pytest

from coda_bio_plugin.fastqc.parser import (
    MODULE_NAMES,
    FastqcParseError,
    parse_fastqc,
)

EXAMPLE = Path("docs/examples/fastqc/fastqc_data.txt")


def test_example_preserves_modules_statuses_and_metadata() -> None:
    report = parse_fastqc(EXAMPLE.read_text(encoding="utf-8"))
    assert report.version == "0.11.9"
    assert tuple(module.name for module in report.modules) == MODULE_NAMES

    duplication = report.find_module("Sequence Duplication Levels")
    assert duplication is not None
    assert duplication.status == "warn"
    assert duplication.metadata == (
        ("Total Deduplicated Percentage", "62.913333333333334"),
    )
    assert duplication.rows[0][0] == "1"

    overrepresented = report.find_module("Overrepresented sequences")
    assert overrepresented is not None
    assert overrepresented.header == ()
    assert overrepresented.rows == ()
    assert report.find_module("not present") is None


def test_empty_modules_and_unknown_modules() -> None:
    report = parse_fastqc(
        "##FastQC\t1.0\n"
        ">>Basic Statistics\tfail\n"
        "#Measure\tValue\n"
        ">>END_MODULE\n"
        ">>Future module\tpass\n"
        "#uninterpreted\tmetadata\n"
        "arbitrary content\n"
        ">>END_MODULE\n"
    )
    assert report.modules[0].rows == ()
    assert report.modules[0].status == "fail"
    assert report.modules[1].raw_lines == (
        "#uninterpreted\tmetadata",
        "arbitrary content",
    )


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", "missing ##FastQC"),
        ("##FastQC\n", "expected ##FastQC"),
        ("##FastQC\t1\noutside\n", "content appears outside"),
        ("##FastQC\t1\n>>END_MODULE\n", "outside a module"),
        ("##FastQC\t1\n>>A\tpass\n", "missing END_MODULE"),
        ("##FastQC\t1\n>>A\tpass\n>>B\tpass\n", "missing END_MODULE"),
        ("##FastQC\t1\n>>A\tbad\n", "invalid status"),
        (
            "##FastQC\t1\n>>A\tpass\n>>END_MODULE\n>>A\twarn\n",
            "duplicate module",
        ),
        (
            "##FastQC\t1\n>>Basic Statistics\tpass\nvalue\n>>END_MODULE\n",
            "before its header",
        ),
        (
            "##FastQC\t1\n>>Basic Statistics\tpass\n#Measure\tWrong\n>>END_MODULE\n",
            "missing columns",
        ),
        (
            "##FastQC\t1\n>>Basic Statistics\tpass\n#Measure\tValue\nx\n>>END_MODULE\n",
            "fields, but its header",
        ),
        (
            "##FastQC\t1\n>>Basic Statistics\tpass\n"
            "#Measure\tValue\nx\t1\nx\t2\n>>END_MODULE\n",
            "duplicate Basic Statistics",
        ),
        (
            "##FastQC\t1\n>>Per base N content\tpass\n"
            "#Base\tN-Count\n1\tnan\n>>END_MODULE\n",
            "must be finite",
        ),
        (
            "##FastQC\t1\n>>Per base N content\tpass\n"
            "#Base\tN-Count\n4-2\t0\n>>END_MODULE\n",
            "invalid range",
        ),
        (
            "##FastQC\t1\n>>Per base N content\tpass\n"
            "#Base\tN-Count\n1\t101\n>>END_MODULE\n",
            "between 0 and 100",
        ),
        (
            "##FastQC\t1\n>>Sequence Length Distribution\tpass\n"
            "#Length\tCount\n10\t-1\n>>END_MODULE\n",
            "non-negative",
        ),
        (
            "##FastQC\t1\n>>Adapter Content\tpass\n#Position\n>>END_MODULE\n",
            "at least one adapter",
        ),
        (
            "##FastQC\t1\n>>Sequence Duplication Levels\twarn\n"
            "#Total Deduplicated Percentage\t50\n"
            "#Total Deduplicated Percentage\t50\n>>END_MODULE\n",
            "duplicate duplication metadata",
        ),
    ],
)
def test_invalid_artifacts_teach(text: str, message: str) -> None:
    with pytest.raises(FastqcParseError, match=message):
        parse_fastqc(text)
