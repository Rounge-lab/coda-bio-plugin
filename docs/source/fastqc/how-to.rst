FastQC how-to
=============

This page covers common tasks for using the FastQC plugin. For complete
parameter and output details, see the :doc:`reference`.

Prepare and verify a FastQC artifact
------------------------------------

FastQC usually writes its report inside a directory named
``fastqc_data.txt``. Extract the file from the FastQC output archive if
necessary, then place it next to the manifest you will create.

From the directory containing ``fastqc_data.txt``, run:

.. code-block:: console

   workflow-coda verify verified-manifest.json fastqc_data.txt \
     --id fastqc \
     --type org.example.fastqc \
     --format bio.fastqc \
     --schema-version 1.0 \
     --producer-name "FastQC" \
     --producer-version 1.0

This creates ``verified-manifest.json`` with a complete artifact declaration.
The artifact format must be ``bio.fastqc``. The artifact type,
``org.example.fastqc`` in this example, is the value layouts use to select the
artifact.

By default, verification requires all ten standard FastQC modules. To require
a subset instead, pass the verifier criteria as JSON with ``--criteria``:

.. code-block:: console

   workflow-coda verify verified-manifest.json fastqc_data.txt \
     --id fastqc \
     --type org.example.fastqc \
     --format bio.fastqc \
     --schema-version 1.0 \
     --producer-name "FastQC" \
     --producer-version 1.0 \
     --criteria '{"required_modules":["Basic Statistics","Per base sequence quality"]}'

The value of ``required_modules`` can be a list of standard module names or a
comma-separated string. An empty list or empty string requires no modules.
Present recognized modules are still validated even when they are not in the
required list. See workflow-coda's
`verification how-to <https://github.com/sverre-branders/workflow-coda/blob/main/docs/source/user/how-to/producing-manifests.rst>`_
for the verifier CLI and manifest details.

Add FastQC components to a layout
---------------------------------

Add component placements to a tab's ``components`` list. Set ``artifact`` to
the artifact's **type** from the manifest, not its artifact id:

.. code-block:: yaml

   schema_version: "0.2.0"
   title: Sequencing report
   tabs:
     - title: FastQC
       components:
         - id: bio.fastqc_overview
           parameters:
             artifact: org.example.fastqc
         - id: bio.fastqc_per_base_sequence_quality
           parameters:
             artifact: org.example.fastqc

The available component IDs are listed in the :doc:`reference`.

Show a chart's data table
-------------------------

The chart components accept ``include_table: true`` to include a disclosure
containing the module's complete data table:

.. code-block:: yaml

   - id: bio.fastqc_per_base_n_content
     parameters:
       artifact: org.example.fastqc
       include_table: true

The table is present in the report even without JavaScript. When enabled, it
provides a complete non-JavaScript alternative to reading the chart. Tables
can increase report size, so include them where readers need the underlying
values. Basic Statistics always renders its table and does not accept
``include_table``.

Choose behavior when data is missing
------------------------------------

A missing artifact or a missing module produces an unavailable outcome for
that placement. To choose whether unavailable placements appear as notices,
are skipped, or cause the build to fail, use workflow-coda's placement
policies. See the framework's
`placement and unavailable policies documentation <https://github.com/sverre-branders/workflow-coda/tree/main/docs/source/user>`_.
