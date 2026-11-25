===============
fastp reference
===============

Artifact format
---------------

fastp artifacts use the ``bio.fastp`` format and contain a UTF-8 JSON
document produced by fastp.

The plugin validates supported fields in recognized sections. Unknown fields
are ignored for forward compatibility. Structural parsing permits absent
top-level sections; verification additionally checks the completeness required
by its configured criteria.

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Aspect
     - Behavior
   * - Counts
     - Supported counts must be non-negative integers. Booleans are rejected.
   * - Rates and content
     - Supported fractions must be finite numbers between zero and one.
   * - Quality curves
     - Supported quality scores must be finite, non-negative numbers.
   * - Curve lengths
     - Every supported curve must contain exactly ``total_cycles`` values.
   * - Insert-size histogram
     - Histogram counts must be non-negative integers. Empty arrays are
       permitted by structural parsing.
   * - Unknown fields
     - Ignored for forward compatibility.
   * - Overrepresented sequences
     - The field must be an object when present. Entry contents remain opaque
       and are not displayed by the components.
   * - Biological quality
     - Components display reported values without assigning QC statuses or
       inventing thresholds.

Recognized top-level sections are:

* ``summary``
* ``filtering_result``
* ``duplication``
* ``insert_size``
* ``adapter_cutting``
* ``read1_before_filtering``
* ``read2_before_filtering``
* ``read1_after_filtering``
* ``read2_after_filtering``
* ``command``

Every recognized section present in the artifact is structurally validated,
including sections that no component placement uses.

Components
----------

Each component requires an artifact whose manifest format is ``bio.fastp``.

.. list-table::
   :header-rows: 1

   * - Component ID
     - Required section
     - Output
   * - ``bio.fastp_overview``
     - ``summary``
     - Before/after metrics table and reported version/sequencing metadata
   * - ``bio.fastp_filtering_result``
     - ``filtering_result``
     - Filtering-outcome count chart
   * - ``bio.fastp_duplication``
     - ``duplication``
     - Reported duplication percentage
   * - ``bio.fastp_insert_size``
     - ``insert_size``
     - Histogram, reported peak, and unknown count
   * - ``bio.fastp_adapter_cutting``
     - ``adapter_cutting``
     - Trimming totals, adapter sequences, and adapter-count tables
   * - ``bio.fastp_quality_curves``
     - Selected read section
     - Per-cycle A, T, C, G, and mean quality curves
   * - ``bio.fastp_content_curves``
     - Selected read section
     - Per-cycle A, T, C, G, N, and GC content curves

Parameters
----------

Every component requires ``artifact``: the artifact **type** declared in the
manifest, not its artifact id. Its manifest format must be ``bio.fastp``.

Every component accepts optional ``caption`` text. Captions must contain
visible text and are escaped when rendered.

The four chart components accept ``include_table`` (boolean, default
``false``). Setting it to ``true`` adds a disclosure containing the complete
chart data table.

The overview, duplication, and adapter-cutting components reject
``include_table``. Their normal output already determines whether tables
are displayed.

Both curve components require ``section``. Its value must be one of:

* ``read1_before_filtering``
* ``read2_before_filtering``
* ``read1_after_filtering``
* ``read2_after_filtering``

Other components reject ``section``. Unknown parameters and invalid parameter
values are rejected before artifact data is accessed.

Output behavior
---------------

.. list-table::
   :header-rows: 1

   * - Situation
     - Behavior
   * - Artifact unavailable
     - The component returns an unavailable outcome with the store's
       explanation.
   * - Required section missing
     - The component returns an unavailable outcome.
   * - Read section with zero cycles
     - The component renders an empty-result notice without loading Plotly.
       Its data-table header is included when requested.
   * - Empty insert-size histogram
     - The component renders an empty-result notice and retains the reported
       peak and unknown count. No Plotly import is required.
   * - Zero filtering counts
     - Supplied outcomes are retained and charted, including zero values.
   * - Optional too-long count
     - Omitted when absent; retained when supplied as zero.
   * - Adapter-count mapping absent
     - Displayed as not reported.
   * - Adapter-count mapping present but empty
     - Displayed as containing no reported entries.
   * - Invalid artifact data
     - Reading or validation raises an artifact-read error rather than
       reporting a missing section.
   * - Tables
     - All supplied chart bins or cycles are retained. Adapter-count tables
       retain all supplied entries.

Chart interpretation
--------------------

Quality scores are displayed as supplied, without an arbitrary upper ceiling
or QC threshold bands. Cycles are numbered starting at one.

Content fractions are converted to percentages. GC overlaps the C and G
series; the lines are not stacked.

Insert-size histogram indices are used as insert sizes, starting at zero.
Zero-count bins are retained. The reported unknown count is displayed
separately and is never added as a histogram bin.

Filtering outcomes display reported counts, without deriving cross-section
totals or QC judgments. Duplication displays the rate reported by fastp,
not a plugin-assigned quality status.

Charts initialize with light-mode styling and include presentation-only
light/dark theme updates.

Preview
-------

The example report includes every fastp component using the bundled JSON
artifact. All chart placements include their data tables. Read 1 curves are
shown before and after filtering.

.. raw:: html

   <iframe
     src="../../_static/previews/fastp.html"
     title="fastp component preview"
     loading="lazy"
     style="width: 100%; height: 800px; border: 1px solid #ddd;">
   </iframe>

`Open the example report in a separate page
<../../_static/previews/fastp.html>`_.
