FastQC how-to
=============

This page covers common tasks for using the FastQC plugin. For complete
parameter and output details, see the
:doc:`FastQC reference <../../reference/content/fastqc>`.

Prepare and verify a FastQC artifact
------------------------------------

FastQC produces an archive of result files ``{sample_name}_fastqc.zip``. This
archive contains the artifact file recognized by ``coda-bio`` named
``fastqc_data.txt``. Extract the archive and use ``workflow-coda`` to generate
a manifest file for the artifact:

From the directory containing ``fastqc_data.txt``, run:

.. code-block:: console

   workflow-coda verify manifest.json fastqc_data.txt \
     --id fastqc \
     --type your.pipeline.fastqc \
     --format bio.fastqc \
     --schema-version 1.0 \
     --producer-name "FastQC" \
     --producer-version 1.0

This creates ``manifest.json`` with a complete artifact declaration, provided
the ``fastqc_data.txt`` file was intact.  The artifact format must be
``bio.fastqc``. The artifact type, ``your.plugin.fastqc`` in this example, is
the value your layout declaration should use to select the artifact.

By default, verification requires all ten standard FastQC modules. To require
a subset instead, pass the verifier criteria as JSON with ``--criteria``:

.. code-block:: console

   workflow-coda verify manifest.json fastqc_data.txt \
     --id fastqc \
     --type your.pipeline.fastqc \
     --format bio.fastqc \
     --schema-version 1.0 \
     --producer-name "FastQC" \
     --producer-version 1.0 \
     --criteria '{"required_modules":["Basic Statistics","Per base sequence quality"]}'

The value of ``required_modules`` can be a list of standard module names or a
comma-separated string. An empty list or empty string requires no modules.
Present recognized modules are still validated even when they are not in the
required list.

Add FastQC components to a layout
---------------------------------

Add component placements to a tab's ``components`` list. Set ``artifact`` to
the artifact's **type** from the manifest (not its artifact id):

.. code-block:: yaml

   schema_version: "0.2.0"
   title: Sequencing report
   tabs:
     - title: FastQC
       components:
         - id: bio.fastqc_overview
           parameters:
             artifact: your.pipeline.fastqc
         - id: bio.fastqc_per_base_sequence_quality
           parameters:
             artifact: your.pipeline.fastqc

The available component IDs are listed in the
:doc:`FastQC reference <../../reference/content/fastqc>`.

Show a chart's data table
-------------------------

The chart components accept the ``include_table: true`` parameter to include a
disclosure containing the module's complete data table:

.. code-block:: yaml

   - id: bio.fastqc_per_base_n_content
     parameters:
       artifact: your.pipeline.fastqc
       include_table: true

The table is always present in the report if declared. Tables can increase
report size, so include them where readers need the underlying values.

Choose behavior when data is missing
------------------------------------

A missing artifact or a missing module produces an unavailable outcome for
that placement. To choose whether unavailable placements appear as notices,
are skipped, or cause the build to fail, use workflow-coda's placement
policies.
