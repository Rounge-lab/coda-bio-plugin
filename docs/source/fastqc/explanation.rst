FastQC design and interpretation
================================

Verification checks supported structure and completeness, not biological
quality. By default, the verifier requires all ten standard FastQC modules;
the ``required_modules`` criterion can change that completeness requirement.
Recognized modules present in the file are validated whether or not they are
required.

FastQC's reported status is authoritative for this plugin. The plugin displays
the ``pass``, ``warn``, or ``fail`` status from each module; it does not
recalculate FastQC's quality decisions. A module with status ``warn`` or
``fail`` is still valid input and does not, by itself, make verification fail.

Charts use the aggregated values in the artifact. They do not reconstruct
per-read observations or infer additional measurements. In particular, the
per-sequence GC chart shows reported counts only; it does not add a theoretical
distribution overlay that is not present in the artifact.

Tables are optional on chart components to let report authors balance detail
against report size. When ``include_table: true`` is enabled, the chart's
disclosure contains the complete data table. That table remains available
without JavaScript, providing a complete non-JavaScript alternative when
included.

The overview separates reported results from missing data. It counts modules
with Pass, Warn, and Fail statuses separately, and lists absent standard
modules as Unavailable. Missing modules are not presented as passing, and
additional modules are listed separately.
