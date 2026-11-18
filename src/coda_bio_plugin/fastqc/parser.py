"""Parse and validate the structural and recognized-module FastQC grammar.

Unknown modules are retained as opaque lines so that additions to FastQC do
not invalidate otherwise readable reports. Recognized modules have their
headers, row widths, and numeric values checked. A module with no rows is a
valid empty result, including when FastQC omits its header entirely.

This parser does not recompute FastQC's pass/warn/fail decisions or require
specific modules to be present. Completeness is the verifier's policy.
"""

import math
import re
from dataclasses import dataclass
from typing import Final

MODULE_NAMES: Final[tuple[str, ...]] = (
    "Basic Statistics",
    "Per base sequence quality",
    "Per sequence quality scores",
    "Per base sequence content",
    "Per sequence GC content",
    "Per base N content",
    "Sequence Length Distribution",
    "Sequence Duplication Levels",
    "Overrepresented sequences",
    "Adapter Content",
)

_HEADERS: Final[dict[str, tuple[str, ...]]] = {
    "Basic Statistics": ("Measure", "Value"),
    "Per base sequence quality": (
        "Base",
        "Mean",
        "Median",
        "Lower Quartile",
        "Upper Quartile",
        "10th Percentile",
        "90th Percentile",
    ),
    "Per sequence quality scores": ("Quality", "Count"),
    "Per base sequence content": ("Base", "G", "A", "T", "C"),
    "Per sequence GC content": ("GC Content", "Count"),
    "Per base N content": ("Base", "N-Count"),
    "Sequence Length Distribution": ("Length", "Count"),
    "Sequence Duplication Levels": (
        "Duplication Level",
        "Percentage of deduplicated",
        "Percentage of total",
    ),
    "Overrepresented sequences": (
        "Sequence",
        "Count",
        "Percentage",
        "Possible Source",
    ),
    "Adapter Content": ("Position",),
}

_PERCENT_COLUMNS: Final[dict[str, frozenset[str]]] = {
    "Per base sequence content": frozenset({"G", "A", "T", "C"}),
    "Per sequence GC content": frozenset({"GC Content"}),
    "Per base N content": frozenset({"N-Count"}),
    "Sequence Duplication Levels": frozenset(
        {"Percentage of deduplicated", "Percentage of total"}
    ),
    "Overrepresented sequences": frozenset({"Percentage"}),
}

_COUNT_COLUMNS: Final[frozenset[str]] = frozenset({"Count"})
_BASE_MODULES: Final[frozenset[str]] = frozenset(
    {
        "Per base sequence quality",
        "Per base sequence content",
        "Per base N content",
        "Adapter Content",
    }
)
_BIN_PATTERN: Final[re.Pattern[str]] = re.compile(r"([0-9]+)(?:-([0-9]+))?")
_DUPLICATION_METADATA: Final[str] = "Total Deduplicated Percentage"


class FastqcParseError(ValueError):
    """The artifact does not conform to the supported FastQC grammar."""


@dataclass(frozen=True, slots=True)
class FastqcModule:
    """One module, preserving its status and, for unknown modules, raw lines."""

    name: str
    status: str
    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    metadata: tuple[tuple[str, str], ...]
    raw_lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FastqcReport:
    """FastQC version and modules in artifact order."""

    version: str
    modules: tuple[FastqcModule, ...]

    def find_module(self, name: str) -> FastqcModule | None:
        """Return a module by its exact FastQC name, if present."""
        return next((module for module in self.modules if module.name == name), None)


def _fail(line: int, message: str) -> FastqcParseError:
    return FastqcParseError(f"FastQC data line {line}: {message}")


def _number(value: str, line: int, label: str) -> float:
    try:
        number = float(value)
    except ValueError as exc:
        raise _fail(line, f"{label} must be numeric, got {value!r}") from exc
    if not math.isfinite(number):
        raise _fail(line, f"{label} must be finite, got {value!r}")
    return number


def _percentage(value: str, line: int, label: str) -> None:
    number = _number(value, line, label)
    if not 0 <= number <= 100:
        raise _fail(line, f"{label} must be between 0 and 100, got {value!r}")


def _bin(value: str, line: int, label: str, minimum: int) -> None:
    match = _BIN_PATTERN.fullmatch(value)
    if match is None:
        raise _fail(line, f"{label} must be an integer or integer range, got {value!r}")
    start = int(match.group(1))
    end = int(match.group(2)) if match.group(2) is not None else start
    if start < minimum or end < start:
        raise _fail(line, f"{label} has an invalid range: {value!r}")


def _validate_header(name: str, header: tuple[str, ...], line: int) -> None:
    required = _HEADERS[name]
    if any(not column.strip() for column in header):
        raise _fail(line, f"{name!r} has an empty column name")
    if len(set(header)) != len(header):
        raise _fail(line, f"{name!r} has duplicate column names")
    if not header or header[0] != required[0]:
        raise _fail(line, f"{name!r} must start with column {required[0]!r}")
    missing = [column for column in required if column not in header]
    if missing:
        raise _fail(line, f"{name!r} is missing columns: {', '.join(missing)}")
    if name == "Adapter Content" and len(header) < 2:
        raise _fail(line, "Adapter Content must name at least one adapter column")


def _validate_row(
    name: str, header: tuple[str, ...], row: tuple[str, ...], line: int
) -> None:
    if len(row) != len(header):
        raise _fail(
            line,
            f"{name!r} has {len(row)} fields, but its header has {len(header)}",
        )
    if not row[0].strip():
        raise _fail(line, f"{name!r} has an empty first field")
    if name in _BASE_MODULES:
        _bin(row[0], line, header[0], 1)
    elif name == "Sequence Length Distribution":
        _bin(row[0], line, header[0], 0)

    for column, value in zip(header, row, strict=True):
        label = f"{name!r} column {column!r}"
        if column in _PERCENT_COLUMNS.get(name, frozenset()):
            _percentage(value, line, label)
        elif name == "Adapter Content" and column != "Position":
            _percentage(value, line, label)
        elif column in _COUNT_COLUMNS:
            if _number(value, line, label) < 0:
                raise _fail(line, f"{label} must be non-negative, got {value!r}")
        elif name == "Per base sequence quality" and column != "Base":
            _number(value, line, label)
        elif name == "Per sequence quality scores" and column == "Quality":
            _number(value, line, label)


def _parse_known_module(
    name: str, status: str, body: list[tuple[int, str]]
) -> FastqcModule:
    header: tuple[str, ...] = ()
    rows: list[tuple[str, ...]] = []
    metadata: list[tuple[str, str]] = []
    measures: set[str] = set()

    for line_number, line in body:
        if line.startswith("#"):
            fields = line[1:].split("\t")
            if name == "Sequence Duplication Levels" and fields[0] == (
                _DUPLICATION_METADATA
            ):
                if len(fields) != 2 or metadata:
                    raise _fail(line_number, "invalid or duplicate duplication metadata")
                _percentage(fields[1], line_number, _DUPLICATION_METADATA)
                metadata.append((fields[0], fields[1]))
                continue
            if header:
                raise _fail(line_number, f"{name!r} has more than one header")
            header = tuple(fields)
            _validate_header(name, header, line_number)
            continue
        if not header:
            raise _fail(line_number, f"{name!r} has a data row before its header")
        row = tuple(line.split("\t"))
        _validate_row(name, header, row, line_number)
        if name == "Basic Statistics":
            if row[0] in measures:
                raise _fail(line_number, f"duplicate Basic Statistics measure {row[0]!r}")
            measures.add(row[0])
        rows.append(row)

    return FastqcModule(
        name=name,
        status=status,
        header=header,
        rows=tuple(rows),
        metadata=tuple(metadata),
        raw_lines=tuple(line for _, line in body),
    )


def _make_module(
    name: str, status: str, body: list[tuple[int, str]]
) -> FastqcModule:
    if name in _HEADERS:
        return _parse_known_module(name, status, body)
    return FastqcModule(
        name=name,
        status=status,
        header=(),
        rows=(),
        metadata=(),
        raw_lines=tuple(line for _, line in body),
    )


def parse_fastqc(text: str) -> FastqcReport:
    """Parse a FastQC data file, raising :class:`FastqcParseError` on failure."""
    lines = text.splitlines()
    if not lines:
        raise _fail(1, "missing ##FastQC version header")
    version_fields = lines[0].split("\t")
    if (
        len(version_fields) != 2
        or version_fields[0] != "##FastQC"
        or not version_fields[1].strip()
    ):
        raise _fail(1, "expected ##FastQC followed by a tab and a version")

    modules: list[FastqcModule] = []
    seen: set[str] = set()
    name: str | None = None
    status = ""
    body: list[tuple[int, str]] = []

    for line_number, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        if line == ">>END_MODULE":
            if name is None:
                raise _fail(line_number, "END_MODULE appears outside a module")
            modules.append(_make_module(name, status, body))
            name = None
            body = []
        elif line.startswith(">>"):
            if name is not None:
                raise _fail(line_number, f"module {name!r} is missing END_MODULE")
            fields = line[2:].split("\t")
            if len(fields) != 2 or not fields[0].strip():
                raise _fail(line_number, "expected a module name and status, separated by a tab")
            name, status = fields
            if name in seen:
                raise _fail(line_number, f"duplicate module {name!r}")
            if status not in {"pass", "warn", "fail"}:
                raise _fail(line_number, f"invalid status {status!r} for module {name!r}")
            seen.add(name)
        elif name is None:
            raise _fail(line_number, "content appears outside a module")
        else:
            body.append((line_number, line))

    if name is not None:
        raise _fail(len(lines), f"module {name!r} is missing END_MODULE")
    return FastqcReport(version=version_fields[1], modules=tuple(modules))
