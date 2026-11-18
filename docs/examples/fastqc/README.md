# FastQC example

With `coda-bio-plugin` and `workflow-coda` installed, build the example from
the repository root:

```sh
workflow-coda build docs/examples/fastqc/manifest.json \
  docs/examples/fastqc/layout.yaml -o fastqc-report.html
```

Every FastQC component accepts two parameters:

- `artifact` (required): the manifest artifact **type**, here
  `org.example.fastqc`. Its declared format must be `bio.fastqc`.
- `caption` (optional): visible text shown after the component content.

Both values must be strings containing visible text; null is not accepted.

Basic Statistics always displays its complete module table when a header is
present and does not accept `include_table`. The other nine module components
accept `include_table` (optional boolean, default `false`). The FastQC overview
does not accept this parameter. When enabled, a module component includes the
complete HTML table for its module. For chart components, this table appears in
a native disclosure as a non-JavaScript alternative to the chart. The
Overrepresented Sequences component is table-only; by default, it shows the
reported status and caption without displaying module rows.

A missing artifact or a missing module produces an unavailable notice. A
present module with no rows instead renders successfully, with its reported
status and an explicit empty-result message. Basic Statistics displays its
header table in this case if a header is present. For the other modules,
enabling `include_table` also displays an empty table when a header is present.
In particular, an empty overrepresented-sequences table does not establish a
general absence of contamination.

Pass, Warn, and Fail are FastQC's reported module statuses, not report-builder
success or failure states. The overview counts the ten standard modules
separately from any additional modules. The GC chart shows only the reported
counts: it does not invent a theoretical reference overlay.
