# FastQC example

With Pixi and the project environment available, run these commands from the
repository root:

```sh
pixi run fastqc-verify
pixi run fastqc-build
```

The verification task creates the manifest used by the build task. The build
writes `fastqc-report.html` in the repository root.

For a guided walkthrough, using your own artifact, component configuration,
and output details, see the [FastQC documentation](../../source/fastqc/index.rst).
