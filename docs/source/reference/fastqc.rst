FastQC reference
================

Artifact format
---------------

FastQC artifacts use the ``bio.fastqc`` format and contain UTF-8 text in the
FastQC ``fastqc_data.txt`` structure: a ``##FastQC`` version header followed
by module sections, each with a name, a ``pass``, ``warn``, or ``fail``
status, a body, and a ``>>END_MODULE`` terminator.

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Aspect
     - Behavior
   * - Structure
     - The version header and module boundaries are checked. Duplicate module
       names, invalid statuses, incomplete sections, and content outside a
       module are rejected.
   * - Recognized modules
     - Headers, row widths, and supported numeric values are validated.
       Additional columns are permitted when the required columns are present.
   * - Unknown modules
     - Retained as opaque content; they do not invalidate an otherwise
       readable report.
   * - Verification
     - The default requires all ten standard modules listed below. The
       ``required_modules`` criterion can select a subset, including an empty
       set.
   * - Result status
     - ``warn`` and ``fail`` are valid FastQC results, not verification
       failures. Verification checks supported structure and completeness,
       not biological quality.

The standard modules, in their report order, are:

#. Basic Statistics
#. Per base sequence quality
#. Per sequence quality scores
#. Per base sequence content
#. Per sequence GC content
#. Per base N content
#. Sequence Length Distribution
#. Sequence Duplication Levels
#. Overrepresented sequences
#. Adapter Content

Every recognized module present in the artifact is validated, including modules
omitted from ``required_modules``. The verifier accepts required module names
from this standard list.

Components
----------

All components use the ``bio.fastqc_`` prefix. Each requires an artifact whose
manifest format is ``bio.fastqc``.

.. table::

   +-----------------------------------------------+--------------------------------+-------------------------+
   | Component ID                                  | FastQC module                  | Output                  |
   +===============================================+================================+=========================+
   | ``bio.fastqc_overview``                       | All standard modules           | Status overview         |
   +-----------------------------------------------+--------------------------------+-------------------------+
   | ``bio.fastqc_basic_statistics``               | Basic Statistics               | Table                   |
   +-----------------------------------------------+--------------------------------+-------------------------+
   | ``bio.fastqc_per_base_sequence_quality``      | Per base sequence quality      | Chart                   |
   +-----------------------------------------------+--------------------------------+-------------------------+
   | ``bio.fastqc_per_sequence_quality_scores``    | Per sequence quality scores    | Chart                   |
   +-----------------------------------------------+--------------------------------+-------------------------+
   | ``bio.fastqc_per_base_sequence_content``      | Per base sequence content      | Chart                   |
   +-----------------------------------------------+--------------------------------+-------------------------+
   | ``bio.fastqc_per_sequence_gc_content``        | Per sequence GC content        | Chart                   |
   +-----------------------------------------------+--------------------------------+-------------------------+
   | ``bio.fastqc_per_base_n_content``             | Per base N content             | Chart                   |
   +-----------------------------------------------+--------------------------------+-------------------------+
   | ``bio.fastqc_sequence_length_distribution``   | Sequence Length Distribution   | Chart                   |
   +-----------------------------------------------+--------------------------------+-------------------------+
   | ``bio.fastqc_sequence_duplication_levels``    | Sequence Duplication Levels    | Chart                   |
   +-----------------------------------------------+--------------------------------+-------------------------+
   | ``bio.fastqc_overrepresented_sequences``      | Overrepresented sequences      | Table                   |
   +-----------------------------------------------+--------------------------------+-------------------------+
   | ``bio.fastqc_adapter_content``                | Adapter Content                | Chart                   |
   +-----------------------------------------------+--------------------------------+-------------------------+

Parameters
----------

Every component requires ``artifact``: the artifact **type** declared in the
manifest. The artifact's format must be ``bio.fastqc``.

Every component also accepts optional ``caption`` text.

The nine module components other than Basic Statistics accept optional
``include_table`` (boolean, default ``false``). For chart components, ``true``
adds a disclosure containing the module's complete data table. The
Overrepresented Sequences component is table-only; its table is not shown by
default. Basic Statistics always renders its table and rejects
``include_table``. The overview also rejects ``include_table``.

Output behavior
---------------

.. table::

   +----------------------+--------------------------------------------------------------------+
   | Situation            | Behavior                                                           |
   +======================+====================================================================+
   | Artifact unavailable | The component returns an unavailable outcome with the store's      |
   |                      | explanation.                                                       |
   +----------------------+--------------------------------------------------------------------+
   | Module missing       | Its individual component returns an unavailable outcome. The       |
   |                      | overview instead lists the module as unavailable.                  |
   +----------------------+--------------------------------------------------------------------+
   | Module present,      | The component renders successfully, shows its reported status,     |
   | with no data rows    | and displays an empty-result message. A table header is rendered  |
   |                      | when available and applicable.                                     |
   +----------------------+--------------------------------------------------------------------+
   | FastQC status        | ``pass``, ``warn``, and ``fail`` are displayed as Pass, Warn, and   |
   |                      | Fail. They are FastQC results, not report-builder errors.          |
   +----------------------+--------------------------------------------------------------------+
   | Tables               | Tables contain the complete supplied module data. Chart tables are |
   |                      | included only when ``include_table: true``.                         |
   +----------------------+--------------------------------------------------------------------+
   | Caption              | Optional visible text is rendered with the component content.      |
   +----------------------+--------------------------------------------------------------------+

For further details about workflow-coda manifest and placement behavior, see
its `manifest production guide <https://github.com/sverre-branders/workflow-coda/blob/main/docs/source/user/how-to/producing-manifests.rst>`_
and `framework documentation <https://github.com/sverre-branders/workflow-coda/tree/main/docs/source/user>`_.
