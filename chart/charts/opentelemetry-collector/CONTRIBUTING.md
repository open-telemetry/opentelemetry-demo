# Collector Chart Contributing Guide

All changes to the chart require a bump to the version in `chart.yaml`. See the [Contributing Guide](https://github.com/open-telemetry/opentelemetry-helm-charts/blob/main/CONTRIBUTING.md#versioning) for our versioning requirements.

Once the chart version is bumped, the examples must be regenerated.  You can regenerate examples by running `make generate-examples CHARTS=opentelemetry-collector`.

## Bumping Default Collector Version

1. Increase the minor version of the chart by one and set the patch version to zero.
2. Update the chart's `appVersion` to match the new collector version.  This version will be used as the image tag by default.
3. Review the corresponding release notes in [Collector Core](https://github.com/open-telemetry/opentelemetry-collector/releases), [Collector Contrib](https://github.com/open-telemetry/opentelemetry-collector-contrib/releases), and [Collector Releases](https://github.com/open-telemetry/opentelemetry-collector-releases/releases).  If any changes affect the helm charts, adjust the helm chart accordingly.
4. Run `make generate-examples CHARTS=opentelemetry-collector`.
