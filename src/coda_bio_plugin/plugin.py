from importlib import metadata

from workflow_coda.components import PluginMetadata
from workflow_coda.plugins import ReportPlugin

from .fastp.verifier import FASTP_VERIFIER
from .fastqc.components import FASTQC_COMPONENTS
from .fastqc.verifier import FASTQC_VERIFIER

SUPPORTED_MANIFEST_SCHEMA_VERSIONS = {"0.3.0"}


def get_plugin() -> ReportPlugin:
    """The coda-bio plugin: officially supported bioinformatics components."""
    return ReportPlugin(
        metadata=PluginMetadata(
            id="bio",
            name="Officially supported bioinformatics report components",
            version=metadata.version("coda-bio-plugin"),
            description=(
                "Officially supported workflow-coda components, specifically "
                "for the field of bioinformatics."
            ),
            supported_schema_versions=frozenset(SUPPORTED_MANIFEST_SCHEMA_VERSIONS),
        ),
        components=FASTQC_COMPONENTS,
        artifact_verifiers=(FASTQC_VERIFIER, FASTP_VERIFIER),
    )
