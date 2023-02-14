# <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" alt="OTel logo" width="45"> + <img src="https://avatars.githubusercontent.com/u/5128994?s=200&amp;v=4" alt="@instana" width="45" height="45"> OpenTelemetry Demo with Instana

This repository contains a custom fork of the OpenTelemetry Astronomy Shop, a microservice-based demo application, integrated with an Instana backend. The demo shows the native Instana OpenTelemetry data collection, correlation of OTel tracing and the underlying monitored infrastructure, or an example of trace continuity between Instana tracing and OpenTelemetry.

To learn more about the demo application please refer to the [upstream README](https://github.com/open-telemetry/opentelemetry-demo/blob/main/README.md) and the [demo documentation](https://opentelemetry.io/docs/demo/) available at the OpenTelemetry project site.

---

**TODO**:

- build (Compose)
- deploy with Compose
- deploy with Helm (on K8S and OpenShift)
- various options:
    * Collector
    * Direct to agent
    * via Collector's Instana exporter and SaaS endpoint
    * ...
- special features
    * Envoy Instana-native instrumentation to who cross-tracer support and context propagation
    * ...

Q: Should we put everything in this README? Or put things in separate files/folders? Or we might use the GitHub WIKI instead and just provide links to the sections from here?

---

## Demo 

Additions and modifications to the upstream demo version include:

- provision and configure demo services for Instana APM monitoring (Instana-native tracing is disabled)
- OTel-enabled Instana agent configuration and docker-compose file (available in the [instana-agent](../instana-agent) folder)
- custom Helm [configuration file](values-instana-agent.yaml) to deploy in Kubernetes (excluding Instana agent deployment)
- provide pre-built custom demo container images
- example Instana-native tracing service instrumentation (to show cross-protocol trace continuity) and OTel contrib library patch for proper downstream service correlation.

## Reporting issues

If you found a bug, have a suggestion or a question regarding the Instana-specific functionality, please open an issue [here](https://github.com/instana/opentelemetry-demo/issues). Problems related to the core demo application should generally be reported via the [upstream OTel Demo project](https://github.com/open-telemetry/opentelemetry-demo/issues). Please read the [troubleshooting tips](troubleshooting.md) before you and issue.

## Contributing
Contributions are welcome - feel free to submit a pull request. You may find useful the upstream [CONTRIBUTING](https://github.com/instana/opentelemetry-demo/blob/main/CONTRIBUTING.md) guidance to get seom general guidance on how to setup a development environment or how to submit a GitHub PR.
