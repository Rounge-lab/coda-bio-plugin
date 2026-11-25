<h1 align="center">
  coda-bio-plugin
</h1>

<h4 align="center">Bioinformatics artifact verification and report components for workflow-coda.</h4>

<p align="center">
  <a href="https://github.com/Rounge-lab/coda-bio-plugin/releases">
    <img src="https://img.shields.io/github/v/release/Rounge-lab/coda-bio-plugin"
         alt="Latest release version">
  </a>
  <a href="https://github.com/Rounge-lab/coda-bio-plugin/actions/workflows/ci.yml">
    <img src="https://github.com/Rounge-lab/coda-bio-plugin/actions/workflows/ci.yml/badge.svg"
         alt="CI status">
  </a>
  <a href="./COPYING">
    <img src="https://img.shields.io/badge/license-GPL--v3.0-blue.svg"
         alt="Licence">
  </a>
</p>

<p align="center">
  <a href="#about-coda-bio-plugin">About coda-bio-plugin</a> •
  <a href="#installation">Installation</a> •
  <a href="#documentation">Documentation</a> •
  <a href="#quick-start">Quick start</a> •
  <a href="#license">License</a> •
  <a href="#citation">Citation</a>
</p>

## About coda-bio-plugin

**coda-bio-plugin** adds bioinformatics artifact verifiers and report
components to [workflow-coda](https://github.com/Rounge-lab/workflow-coda).

Use it to validate supported **FastQC** and **fastp** reports and present
their results as summaries, tables, and interactive charts in a
self-contained HTML report.

The plugin integrates through workflow-coda's plugin entry point. Once
installed in the same environment, its artifact formats and components are
available to `workflow-coda verify` and `workflow-coda build`.

| Tool | Artifact format | Input | Report components |
|---|---|---|---|
| FastQC | `bio.fastqc` | `fastqc_data.txt` | Status overview, statistics, quality and content charts, and sequence tables |
| fastp | `bio.fastp` | JSON report | Before/after metrics, filtering outcomes, duplication, insert sizes, adapter trimming, and per-cycle curves |

Verification checks supported structure and configured completeness, not
biological quality. FastQC's reported Pass, Warn, and Fail statuses remain
valid results. fastp components display reported values without inventing
QC statuses or thresholds.

## Installation

> [!NOTE]
> Requires **Python 3.14 or later**. Install the plugin in the same
> environment as workflow-coda. Chart rendering requires Plotly.

### Latest release

1. Download the wheel (`.whl`) from the
   [latest release](https://github.com/Rounge-lab/coda-bio-plugin/releases/latest).
2. Install the downloaded file:

```bash
python -m pip install /path/to/coda_bio_plugin-<version>-py3-none-any.whl
```

The plugin declares workflow-coda as a dependency. If workflow-coda is not
available from your configured package index, install a compatible
workflow-coda release first.

### From the repository

```bash
git clone https://github.com/Rounge-lab/coda-bio-plugin.git
cd coda-bio-plugin
python -m pip install .
```

### Development and local documentation

Install [Pixi](https://pixi.sh), then run from the repository root:

```bash
pixi install
pixi run test
```

The development environment installs coda-bio-plugin in editable mode and
uses the workflow-coda version pinned in `pyproject.toml`.

To build the documentation and bundled report previews:

```bash
pixi run -e docs docs
```

Open `docs/build/html/index.html` in your browser.

The documentation build verifies each bundled example before generating its
preview report. To build the previews separately:

```bash
pixi run -e docs docs-preview-fastqc
pixi run -e docs docs-preview-fastp
```

Generated reports are written to `docs/source/_static/previews/`. Open them
in a browser to inspect components, charts, data tables, and light/dark
presentation.

To remove the documentation build and generated HTML previews:

```bash
pixi run -e docs docs-clean
```

## Documentation

The documentation includes reference pages, how-to guides, and embedded
all-component previews for both supported tools.

- [FastQC reference](docs/source/reference/content/fastqc.rst)
- [FastQC how-to](docs/source/user-guide/content/fastqc-how-to.rst)
- [fastp reference](docs/source/reference/content/fastp.rst)
- [fastp how-to](docs/source/user-guide/content/fastp-how-to.rst)

Build the documentation locally for rendered pages and interactive previews.

For manifests, layouts, placement policies, and report-building behavior,
see the [workflow-coda documentation](https://workflow-coda.readthedocs.io/en/latest/).

## Quick start

### 1. Verify an artifact

For FastQC, extract `fastqc_data.txt` from the result archive. From the
directory containing that file, run:

```bash
workflow-coda verify manifest.json fastqc_data.txt \
  --id fastqc \
  --type your.pipeline.fastqc \
  --format bio.fastqc \
  --schema-version 1.0 \
  --producer-name "FastQC" \
  --producer-version 1.0
```

For fastp, use its JSON report:

```bash
workflow-coda verify manifest.json fastp.json \
  --id fastp \
  --type your.pipeline.fastp \
  --format bio.fastp \
  --schema-version 1.0 \
  --producer-name "fastp" \
  --producer-version 1.0
```

Choose the command for your artifact and replace the producer version with
the version used to generate it. Successful verification produces a
complete artifact declaration in `manifest.json`.

### 2. Declare a layout

For a verified fastp artifact, save this as `layout.yaml`:

```yaml
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
          include_table: true

      - id: bio.fastp_quality_curves
        parameters:
          artifact: your.pipeline.fastp
          section: read1_before_filtering
```

The `artifact` parameter selects the manifest artifact's **type**, not its
id or file path.

For FastQC, use components such as `bio.fastqc_overview` and
`bio.fastqc_per_base_sequence_quality`, selecting
`artifact: your.pipeline.fastqc`.

### 3. Build the report

```bash
workflow-coda build manifest.json layout.yaml -o report.html
```

Open `report.html` in your browser.

Chart components can include complete data tables with
`include_table: true`. fastp curve components also require a read-section
selection. See the tool-specific reference pages for accepted parameters
and missing-data behavior.

## License

**coda-bio-plugin** is provided under the GNU
[General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.en.html)
(GPLv3).

It is free software, and you are welcome to redistribute it and/or modify
it under the conditions of the GPLv3 terms. This software is provided
“As is” and comes with ABSOLUTELY NO WARRANTY.

See [COPYING](./COPYING) for the full license text.

## Citation

Branders S, *coda-bio-plugin*, **GitHub**
`https://github.com/Rounge-lab/coda-bio-plugin`
