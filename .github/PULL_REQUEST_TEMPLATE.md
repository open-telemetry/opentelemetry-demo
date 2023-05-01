# Changes

Please provide a brief description of the changes here.

## Merge Requirements

For new features contributions please make sure you have completed the following
essential items:

* [ ] `CHANGELOG.md` updated to document new feature additions
* [ ] Appropriate documentation updates in the [docs][]
* [ ] Appropriate Helm chart updates in the [helm-charts][]

<!--
A Pull Request that modifies instrumentation code will likely require an
update in docs. Please make sure to update the opentelemetry.io repo with any
docs changes.

A Pull Request that modifies docker-compose.yaml, otelcol-config.yaml, or
Grafana dashboards, will likely require an update to the Demo Helm chart.
Other changes affecting how a service is deployed will also likely require an
update to the Demo Helm chart.
-->

Maintainers will not merge until the above have been completed. If you're unsure
which docs need to be changed ping the
[@open-telemetry/demo-approvers](https://github.com/orgs/open-telemetry/teams/demo-approvers).

[docs]: https://opentelemetry.io/docs/demo/
[helm-charts]: https://github.com/open-telemetry/opentelemetry-helm-charts
