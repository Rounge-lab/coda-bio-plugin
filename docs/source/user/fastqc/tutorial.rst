Build your first FastQC report
==============================

This tutorial walks through one successful report build using the repository's
bundled FastQC example.

Prerequisites
-------------

You will need `Pixi <https://pixi.sh/>`_, the project environment, and the
FastQC example data included in this repository. Run the commands below from
the repository root.

Build the report
----------------

First verify the bundled artifact, then build the report from the generated
manifest:

.. code-block:: console

   pixi run fastqc-verify
   pixi run fastqc-build

The verification task writes
``docs/examples/fastqc/verified-manifest.json``. The build task uses that
manifest and ``docs/examples/fastqc/layout.yaml`` to write
``fastqc-report.html`` in the repository root. These are separate tasks; run
verification before building.

Inspect the report
------------------

Open ``fastqc-report.html`` in a browser. In the FastQC tab, inspect the
overview and a chart such as **Per base sequence quality**. The overview
summarizes the statuses FastQC reported for its standard modules. Charts
visualize the values in the artifact.

Open the **Diagnostics** tab to see build-time diagnostics. For this example,
the default theme and omitted logo and favicon may be noted there; these notes
do not mean FastQC verification failed.

You have produced a self-contained report from a verified FastQC artifact.
To use your own ``fastqc_data.txt`` file and configure the report, continue to
the :doc:`how-to`.
