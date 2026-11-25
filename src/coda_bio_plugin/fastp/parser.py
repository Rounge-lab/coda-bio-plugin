"""Validate decoded fastp JSON.

JSON decoding and artifact IO belong to workflow-coda. This module
accepts decoded JSON and validates the supported fastp fields.

Top-level completeness belongs to the verifier. Recognized sections
are validated when present; unknown fields are ignored for forward
compatibility.

Overrepresented sequence entries remain opaque until their non-empty
structure is supported explicitly.
"""

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from workflow_coda.manifest import JsonValue


class FastpParseError(ValueError):
    """Decoded JSON violates the supported fastp structure."""


@dataclass(frozen=True, slots=True)
class FastpSummaryMetrics:
    total_reads: int
    total_bases: int
    q20_bases: int
    q30_bases: int
    q20_rate: float
    q30_rate: float
    read1_mean_length: float
    gc_content: float
    read2_mean_length: float | None = None


@dataclass(frozen=True, slots=True)
class FastpSummary:
    before_filtering: FastpSummaryMetrics
    after_filtering: FastpSummaryMetrics
    fastp_version: str | None = None
    sequencing: str | None = None


@dataclass(frozen=True, slots=True)
class FastpFilteringResult:
    passed_filter_reads: int
    low_quality_reads: int
    too_many_n_reads: int
    too_short_reads: int
    too_long_reads: int | None = None


@dataclass(frozen=True, slots=True)
class FastpDuplication:
    rate: float


@dataclass(frozen=True, slots=True)
class FastpInsertSize:
    peak: int
    unknown: int
    histogram: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class FastpAdapterCutting:
    adapter_trimmed_reads: int
    adapter_trimmed_bases: int
    read1_adapter_sequence: str | None
    read2_adapter_sequence: str | None
    read1_adapter_counts: Mapping[str, int] | None
    read2_adapter_counts: Mapping[str, int] | None


@dataclass(frozen=True, slots=True)
class FastpRead:
    total_reads: int
    total_bases: int
    q20_bases: int
    q30_bases: int
    q40_bases: int | None
    total_cycles: int
    quality_curves: Mapping[str, tuple[float, ...]]
    content_curves: Mapping[str, tuple[float, ...]]
    kmer_count: Mapping[str, int] | None


@dataclass(frozen=True, slots=True)
class FastpReport:
    """Validated sections; absent optional data is represented by None.

    ``sections`` records recognized top-level sections present in the
    source, for subsequent verifier completeness checks.
    """

    sections: frozenset[str]
    summary: FastpSummary | None
    filtering_result: FastpFilteringResult | None
    duplication: FastpDuplication | None
    insert_size: FastpInsertSize | None
    adapter_cutting: FastpAdapterCutting | None
    read1_before_filtering: FastpRead | None
    read2_before_filtering: FastpRead | None
    read1_after_filtering: FastpRead | None
    read2_after_filtering: FastpRead | None
    command: str | None


READ_SECTIONS: Final[tuple[str, ...]] = (
    "read1_before_filtering",
    "read2_before_filtering",
    "read1_after_filtering",
    "read2_after_filtering",
)

SUPPORTED_SECTIONS: Final[frozenset[str]] = frozenset(
    (
        "summary",
        "filtering_result",
        "duplication",
        "insert_size",
        "adapter_cutting",
        *READ_SECTIONS,
        "command",
    )
)


def _object(value: JsonValue, path: str) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise FastpParseError(f"{path}: expected an object")
    return value


def _required(source: Mapping[str, JsonValue], key: str, path: str) -> JsonValue:
    if key not in source:
        raise FastpParseError(f"{path}.{key}: required field is missing")
    return source[key]


def _count(value: JsonValue, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise FastpParseError(f"{path}: expected a non-negative integer")
    return value


def _number(value: JsonValue, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FastpParseError(f"{path}: expected a finite number")
    try:
        number = float(value)
    except OverflowError as exc:
        raise FastpParseError(f"{path}: expected a finite number") from exc
    if not math.isfinite(number):
        raise FastpParseError(f"{path}: expected a finite number")
    return number


def _nonnegative(value: JsonValue, path: str) -> float:
    number = _number(value, path)
    if number < 0:
        raise FastpParseError(f"{path}: expected a non-negative number")
    return number


def _fraction(value: JsonValue, path: str) -> float:
    number = _number(value, path)
    if not 0 <= number <= 1:
        raise FastpParseError(f"{path}: expected a fraction between 0 and 1")
    return number


def _string(value: JsonValue, path: str) -> str:
    if not isinstance(value, str):
        raise FastpParseError(f"{path}: expected a string")
    return value


def _optional[T](
    source: Mapping[str, JsonValue],
    key: str,
    path: str,
    parse: Callable[[JsonValue, str], T],
) -> T | None:
    if key not in source:
        return None
    return parse(source[key], f"{path}.{key}")


def _required_count(source: Mapping[str, JsonValue], key: str, path: str) -> int:
    return _count(_required(source, key, path), f"{path}.{key}")


def _counts(value: JsonValue, path: str) -> Mapping[str, int]:
    source = _object(value, path)
    return MappingProxyType(
        {key: _count(item, f"{path}[{key!r}]") for key, item in source.items()}
    )


def _summary_metrics(value: JsonValue, path: str) -> FastpSummaryMetrics:
    source = _object(value, path)

    def number(key: str, parse: Callable[[JsonValue, str], float]) -> float:
        return parse(_required(source, key, path), f"{path}.{key}")

    return FastpSummaryMetrics(
        total_reads=_required_count(source, "total_reads", path),
        total_bases=_required_count(source, "total_bases", path),
        q20_bases=_required_count(source, "q20_bases", path),
        q30_bases=_required_count(source, "q30_bases", path),
        q20_rate=number("q20_rate", _fraction),
        q30_rate=number("q30_rate", _fraction),
        read1_mean_length=number("read1_mean_length", _nonnegative),
        gc_content=number("gc_content", _fraction),
        read2_mean_length=_optional(source, "read2_mean_length", path, _nonnegative),
    )


def _summary(value: JsonValue, path: str) -> FastpSummary:
    source = _object(value, path)
    return FastpSummary(
        before_filtering=_summary_metrics(
            _required(source, "before_filtering", path),
            f"{path}.before_filtering",
        ),
        after_filtering=_summary_metrics(
            _required(source, "after_filtering", path),
            f"{path}.after_filtering",
        ),
        fastp_version=_optional(source, "fastp_version", path, _string),
        sequencing=_optional(source, "sequencing", path, _string),
    )


def _filtering(value: JsonValue, path: str) -> FastpFilteringResult:
    source = _object(value, path)
    return FastpFilteringResult(
        passed_filter_reads=_required_count(source, "passed_filter_reads", path),
        low_quality_reads=_required_count(source, "low_quality_reads", path),
        too_many_n_reads=_required_count(source, "too_many_N_reads", path),
        too_short_reads=_required_count(source, "too_short_reads", path),
        too_long_reads=_optional(source, "too_long_reads", path, _count),
    )


def _duplication(value: JsonValue, path: str) -> FastpDuplication:
    source = _object(value, path)
    return FastpDuplication(
        rate=_fraction(_required(source, "rate", path), f"{path}.rate")
    )


def _insert_size(value: JsonValue, path: str) -> FastpInsertSize:
    source = _object(value, path)
    histogram = _required(source, "histogram", path)
    if not isinstance(histogram, list):
        raise FastpParseError(f"{path}.histogram: expected an array")
    return FastpInsertSize(
        peak=_required_count(source, "peak", path),
        unknown=_required_count(source, "unknown", path),
        histogram=tuple(
            _count(item, f"{path}.histogram[{index}]")
            for index, item in enumerate(histogram)
        ),
    )


def _adapter_cutting(value: JsonValue, path: str) -> FastpAdapterCutting:
    source = _object(value, path)
    return FastpAdapterCutting(
        adapter_trimmed_reads=_required_count(source, "adapter_trimmed_reads", path),
        adapter_trimmed_bases=_required_count(source, "adapter_trimmed_bases", path),
        read1_adapter_sequence=_optional(
            source, "read1_adapter_sequence", path, _string
        ),
        read2_adapter_sequence=_optional(
            source, "read2_adapter_sequence", path, _string
        ),
        read1_adapter_counts=_optional(source, "read1_adapter_counts", path, _counts),
        read2_adapter_counts=_optional(source, "read2_adapter_counts", path, _counts),
    )


def _curves(
    value: JsonValue,
    path: str,
    *,
    names: tuple[str, ...],
    cycles: int,
    parse: Callable[[JsonValue, str], float],
) -> Mapping[str, tuple[float, ...]]:
    source = _object(value, path)
    curves: dict[str, tuple[float, ...]] = {}
    for name in names:
        values = _required(source, name, path)
        curve_path = f"{path}.{name}"
        if not isinstance(values, list):
            raise FastpParseError(f"{curve_path}: expected an array")
        if len(values) != cycles:
            raise FastpParseError(
                f"{curve_path}: expected {cycles} values to match "
                f"total_cycles, got {len(values)}"
            )
        curves[name] = tuple(
            parse(item, f"{curve_path}[{index}]") for index, item in enumerate(values)
        )
    return MappingProxyType(curves)


def _read(value: JsonValue, path: str) -> FastpRead:
    source = _object(value, path)
    cycles = _required_count(source, "total_cycles", path)

    # Empty objects are valid; non-empty entry semantics are not yet
    # modeled. Do not claim to validate their internal schema.
    if "overrepresented_sequences" in source:
        _object(
            source["overrepresented_sequences"],
            f"{path}.overrepresented_sequences",
        )

    return FastpRead(
        total_reads=_required_count(source, "total_reads", path),
        total_bases=_required_count(source, "total_bases", path),
        q20_bases=_required_count(source, "q20_bases", path),
        q30_bases=_required_count(source, "q30_bases", path),
        q40_bases=_optional(source, "q40_bases", path, _count),
        total_cycles=cycles,
        quality_curves=_curves(
            _required(source, "quality_curves", path),
            f"{path}.quality_curves",
            names=("A", "T", "C", "G", "mean"),
            cycles=cycles,
            parse=_nonnegative,
        ),
        content_curves=_curves(
            _required(source, "content_curves", path),
            f"{path}.content_curves",
            names=("A", "T", "C", "G", "N", "GC"),
            cycles=cycles,
            parse=_fraction,
        ),
        kmer_count=_optional(source, "kmer_count", path, _counts),
    )


def parse_fastp(payload: JsonValue) -> FastpReport:
    """Validate recognized sections of decoded fastp JSON.

    Missing top-level sections are allowed, including an empty object.
    This is structural parsing, not artifact completeness verification.
    """
    source = _object(payload, "fastp")

    def section[T](name: str, parse: Callable[[JsonValue, str], T]) -> T | None:
        if name not in source:
            return None
        return parse(source[name], name)

    return FastpReport(
        sections=frozenset(source).intersection(SUPPORTED_SECTIONS),
        summary=section("summary", _summary),
        filtering_result=section("filtering_result", _filtering),
        duplication=section("duplication", _duplication),
        insert_size=section("insert_size", _insert_size),
        adapter_cutting=section("adapter_cutting", _adapter_cutting),
        read1_before_filtering=section("read1_before_filtering", _read),
        read2_before_filtering=section("read2_before_filtering", _read),
        read1_after_filtering=section("read1_after_filtering", _read),
        read2_after_filtering=section("read2_after_filtering", _read),
        command=section("command", _string),
    )
