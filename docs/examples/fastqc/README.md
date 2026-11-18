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

All ten module components additionally accept `include_table` (optional
boolean, default `false`). The FastQC overview does not accept this parameter.
When enabled, the component includes the complete HTML table for its module.
For chart components, this table appears in a native disclosure as a
non-JavaScript alternative to the chart. The Basic Statistics and
Overrepresented Sequences components are table-only; by default, they show
the reported status and caption without displaying module rows.

A missing artifact or a missing module produces an unavailable notice. A
present module with no rows instead renders successfully, with its reported
status and an explicit empty-result message. If a header is present, enabling
`include_table` also displays that empty table. In particular, an empty
overrepresented-sequences table does not establish a general absence of
contamination.

Pass, Warn, and Fail are FastQC's reported module statuses, not report-builder
success or failure states. The overview counts the ten standard modules
separately from any additional modules. The GC chart shows only the reported
counts: it does not invent a theoretical reference overlay.
