============
fastp how-to
============

This page covers common tasks for using fastp components. For complete
parameter and output details, see the
:doc:`fastp reference <../../reference/content/fastp>`.

Prepare and verify a fastp artifact
-----------------------------------

Use the JSON report produced by fastp, commonly named ``fastp.json``.

From the directory containing the report, run:

.. code-block:: console

   workflow-coda verify manifest.json fastp.json \
     --id fastp \
     --type your.pipeline.fastp \
     --format bio.fastp \
     --schema-version 1.0 \
     --producer-name "fastp" \
     --producer-version 1.0

Replace the producer version with the version used to produce your artifact.

Successful verification creates a complete artifact declaration in
``manifest.json``. The artifact format must be ``bio.fastp``. The artifact
type, ``your.pipeline.fastp`` in this example, is the value used by component
placements to select the artifact.

Add fastp components to a layout
--------------------------------

Add placements to a tab's ``components`` list:

.. code-block:: yaml

   schema_version: "0.4.0"
   title: Sequencing report
   tabs:
     - title: fastp
       components:
         - id: bio.fastp_overview
           parameters:
             artifact: your.pipeline.fastp

         - id: bio.fastp_filtering_result
           parameters:
             artifact: your.pipeline.fastp

         - id: bio.fastp_adapter_cutting
           parameters:
             artifact: your.pipeline.fastp

Set ``artifact`` to the manifest artifact's **type**, not its id.

The available component IDs are listed in the
:doc:`fastp reference <../../reference/content/fastp>`.

Select read curves
------------------

Quality and content curve components require a ``section`` parameter:

.. code-block:: yaml

   - id: bio.fastp_quality_curves
     parameters:
       artifact: your.pipeline.fastp
       section: read1_before_filtering

   - id: bio.fastp_content_curves
     parameters:
       artifact: your.pipeline.fastp
       section: read1_after_filtering

For paired-end reports, select ``read2_before_filtering`` or
``read2_after_filtering`` to display read 2.

To compare before and after filtering, place the same component more than
once with different section values.

Show a chart's data table
-------------------------

All four chart components accept ``include_table: true``:

.. code-block:: yaml

   - id: bio.fastp_insert_size
     parameters:
       artifact: your.pipeline.fastp
       include_table: true

   - id: bio.fastp_quality_curves
     parameters:
       artifact: your.pipeline.fastp
       section: read1_after_filtering
       include_table: true

The disclosure contains all chart bins or cycles. Tables can increase report
size, so include them where readers need the underlying values.

The overview and adapter-cutting components display their normal tables
without this parameter. They reject ``include_table``, as does duplication.

Add explanatory captions
-------------------------

Every component accepts optional visible caption text:

.. code-block:: yaml

   - id: bio.fastp_duplication
     parameters:
       artifact: your.pipeline.fastp
       caption: Duplication rate reported by fastp for this sample.

Captions are escaped as text rather than interpreted as HTML.
