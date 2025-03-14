<img width="1545" alt="nr-hearts-otel" src="https://github.com/user-attachments/assets/96fb9c0e-3cc3-4319-9025-fa4a6fc48f0f">

## New Relic’s Fork of the OpenTelemetry Astronomy Shop

Welcome to New Relic’s fork of the [OpenTelemetry Astronomy Shop](https://opentelemetry.io/ecosystem/demo/)!
This app is a microservice-based distributed system intended to illustrate the
implementation of OpenTelemetry in a near real-world environment. To view the
original repo README, scroll down or click [this link](https://github.com/newrelic/opentelemetry-demo/tree/main?tab=readme-ov-file#-opentelemetry-demo).

After you follow our [quick start instructions](https://github.com/newrelic/opentelemetry-demo?tab=readme-ov-file#quick-start-with-new-relic) 
to deploy the app, check out [how to navigate the OTLP data in your New Relic account](https://github.com/newrelic/opentelemetry-demo?tab=readme-ov-file#navigate-your-otlp-data-in-new-relic)! 

### Modifications
Please note the following modifications to our fork:
* The .env file contains New Relic-specific environment variables so you can quickly
ship the data to your account
* By default, the `recommendationservice` is instrumented with the OTel SDK. An [optional install step](https://github.com/newrelic/opentelemetry-demo/blob/main/docs/kubernetes_deployment.md#new-relic-overrides-optional) has been added that will instrument the `recommendationservice` with the New Relic Python APM 
agent to demonstrate interoperability between our language agents and OpenTelemetry 
instrumentation.

### Quick start with New Relic
Get started quickly by running the app according to your deployment method preference:

* [Docker](https://github.com/newrelic/opentelemetry-demo/blob/main/docs/docker_deployment.md)
* [Kubernetes](https://github.com/newrelic/opentelemetry-demo/blob/main/docs/kubernetes_deployment.md)

Requirements: A New Relic account – [sign up for a free account](https://newrelic.com/signup) if you need one.

### Navigate OTLP data in New Relic
The Demo comes with a number of problem scenarios that you can enable via 
a [feature flag](https://opentelemetry.io/docs/demo/feature-flags/); please 
note that some of these are currently still under testing on our end. 

We are working on [tutorials](https://github.com/newrelic/opentelemetry-demo/blob/main/docs/demo-scenarios/README.md) 
to show you how to troubleshoot these scenarios in New Relic. 

In the meantime, check out our [documentation](https://docs.newrelic.com/docs/opentelemetry/best-practices/opentelemetry-data-overview/) 
to learn how to navigate your OpenTelemetry traces, metrics, and logs in New Relic. 

### Roadmap
Similar to how the Astronomy Shop is under active development, we are also actively
developing and maintaining our fork. Here are a few things we have are working on, or
have planned for the near future:
* [Demo scenario feature flags](https://opentelemetry.io/docs/demo/feature-flags/) are in testing
* [Troubleshooting tutorials](https://github.com/newrelic/opentelemetry-demo/blob/main/docs/demo-scenarios/README.md) for each demo scenario
* Support for OTel-sourced Kubernetes infrastructure metrics in New Relic
* Add a feature flag to enable NR instrumentation for recommendationservice when 
using Docker quick start method

Have a suggestion, or running into problems with our fork? Please let us know by
[opening an issue](https://github.com/newrelic/opentelemetry-demo/issues/new/choose)!

### Contributors
* [Brad Schmitt](https://github.com/bpschmitt)
* [Mir Ansar](https://github.com/miransar)
* [Daniel Kim](https://github.com/lazyplatypus)
* [Krzysztof Spikowski](https://github.com/greenszpila)
* [Ugur Türkarslan](https://github.com/utr1903)
* [Alan West](https://github.com/alanwest)
* [Justin Eveland](https://github.com/jbeveland27)
* [Reese Lee](https://github.com/reese-lee)

-----------

<!-- markdownlint-disable-next-line -->
# <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" alt="OTel logo" width="45"> OpenTelemetry Demo

[![Slack](https://img.shields.io/badge/slack-@cncf/otel/demo-brightgreen.svg?logo=slack)](https://cloud-native.slack.com/archives/C03B4CWV4DA)
[![Version](https://img.shields.io/github/v/release/open-telemetry/opentelemetry-demo?color=blueviolet)](https://github.com/open-telemetry/opentelemetry-demo/releases)
[![Commits](https://img.shields.io/github/commits-since/open-telemetry/opentelemetry-demo/latest?color=ff69b4&include_prereleases)](https://github.com/open-telemetry/opentelemetry-demo/graphs/commit-activity)
[![Downloads](https://img.shields.io/docker/pulls/otel/demo)](https://hub.docker.com/r/otel/demo)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg?color=red)](https://github.com/open-telemetry/opentelemetry-demo/blob/main/LICENSE)
[![Integration Tests](https://github.com/open-telemetry/opentelemetry-demo/actions/workflows/run-integration-tests.yml/badge.svg)](https://github.com/open-telemetry/opentelemetry-demo/actions/workflows/run-integration-tests.yml)
[![Artifact Hub](https://img.shields.io/endpoint?url=https://artifacthub.io/badge/repository/opentelemetry-demo)](https://artifacthub.io/packages/helm/opentelemetry-helm/opentelemetry-demo)
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/9247/badge)](https://www.bestpractices.dev/en/projects/9247)

## Welcome to the OpenTelemetry Astronomy Shop Demo

This repository contains the OpenTelemetry Astronomy Shop, a microservice-based
distributed system intended to illustrate the implementation of OpenTelemetry in
a near real-world environment.

Our goals are threefold:

- Provide a realistic example of a distributed system that can be used to
  demonstrate OpenTelemetry instrumentation and observability.
- Build a base for vendors, tooling authors, and others to extend and
  demonstrate their OpenTelemetry integrations.
- Create a living example for OpenTelemetry contributors to use for testing new
  versions of the API, SDK, and other components or enhancements.

We've already made [huge
progress](https://github.com/open-telemetry/opentelemetry-demo/blob/main/CHANGELOG.md),
and development is ongoing. We hope to represent the full feature set of
OpenTelemetry across its languages in the future.

If you'd like to help (**which we would love**), check out our [contributing
guidance](./CONTRIBUTING.md).

If you'd like to extend this demo or maintain a fork of it, read our
[fork guidance](https://opentelemetry.io/docs/demo/forking/).

## Quick start

You can be up and running with the demo in a few minutes. Check out the docs for
your preferred deployment method:

- [Docker](https://github.com/newrelic/opentelemetry-demo/blob/main/docs/docker_deployment.md)
- [Kubernetes](https://github.com/newrelic/opentelemetry-demo/blob/main/docs/kubernetes_deployment.md)

## Documentation

For detailed documentation, see [Demo Documentation][docs]. If you're curious
about a specific feature, the [docs landing page][docs] can point you in the
right direction.

## Demos featuring the Astronomy Shop

We welcome any vendor to fork the project to demonstrate their services and
adding a link below. The community is committed to maintaining the project and
keeping it up to date for you.

|                           |                |                                  |
|---------------------------|----------------|----------------------------------|
| [AlibabaCloud LogService] | [Elastic]      | [OpenSearch]                     |
| [AppDynamics]             | [Google Cloud] | [Oracle]                         |
| [Aspecto]                 | [Grafana Labs] | [Sentry]                         |
| [Axiom]                   | [Guance]       | [ServiceNow Cloud Observability] |
| [Axoflow]                 | [Honeycomb.io] | [Splunk]                         |
| [Azure Data Explorer]     | [Instana]      | [Sumo Logic]                     |
| [Coralogix]               | [Kloudfuse]    | [TelemetryHub]                   |
| [Dash0]                   | [Liatrio]      | [Teletrace]                      |
| [Datadog]                 | [Logz.io]      | [Tracetest]                      |
| [Dynatrace]               | [New Relic]    | [Uptrace]                        |

## Contributing

To get involved with the project see our [CONTRIBUTING](CONTRIBUTING.md)
documentation. Our [SIG Calls](CONTRIBUTING.md#join-a-sig-call) are every other
Wednesday at 8:30 AM PST and anyone is welcome.

## Project leadership

[Maintainers](https://github.com/open-telemetry/community/blob/main/guides/contributor/membership.md#maintainer)
([@open-telemetry/demo-maintainers](https://github.com/orgs/open-telemetry/teams/demo-maintainers)):

- [Juliano Costa](https://github.com/julianocosta89), Datadog
- [Mikko Viitanen](https://github.com/mviitane), Dynatrace
- [Pierre Tessier](https://github.com/puckpuck), Honeycomb

[Approvers](https://github.com/open-telemetry/community/blob/main/guides/contributor/membership.md#approver)
([@open-telemetry/demo-approvers](https://github.com/orgs/open-telemetry/teams/demo-approvers)):

- [Cedric Ziel](https://github.com/cedricziel) Grafana Labs
- [Penghan Wang](https://github.com/wph95), AppDynamics
- [Reiley Yang](https://github.com/reyang), Microsoft
- [Roger Coll](https://github.com/rogercoll), Elastic
- [Ziqi Zhao](https://github.com/fatsheep9146), Alibaba

Emeritus:

- [Austin Parker](https://github.com/austinlparker)
- [Carter Socha](https://github.com/cartersocha)
- [Michael Maxwell](https://github.com/mic-max)
- [Morgan McLean](https://github.com/mtwo)

### Thanks to all the people who have contributed

[![contributors](https://contributors-img.web.app/image?repo=open-telemetry/opentelemetry-demo)](https://github.com/open-telemetry/opentelemetry-demo/graphs/contributors)

[docs]: https://opentelemetry.io/docs/demo/

<!-- Links for Demos featuring the Astronomy Shop section -->

[AlibabaCloud LogService]: https://github.com/aliyun-sls/opentelemetry-demo
[AppDynamics]: https://community.appdynamics.com/t5/Knowledge-Base/How-to-observe-OpenTelemetry-demo-app-in-Splunk-AppDynamics/ta-p/58584
[Aspecto]: https://github.com/aspecto-io/opentelemetry-demo
[Axiom]: https://play.axiom.co/axiom-play-qf1k/dashboards/otel.traces.otel-demo-traces
[Axoflow]: https://axoflow.com/opentelemetry-support-in-more-detail-in-axosyslog-and-syslog-ng/
[Azure Data Explorer]: https://github.com/Azure/Azure-kusto-opentelemetry-demo
[Coralogix]: https://coralogix.com/blog/configure-otel-demo-send-telemetry-data-coralogix
[Dash0]: https://github.com/dash0hq/opentelemetry-demo
[Datadog]: https://docs.datadoghq.com/opentelemetry/guide/otel_demo_to_datadog
[Dynatrace]: https://www.dynatrace.com/news/blog/opentelemetry-demo-application-with-dynatrace/
[Elastic]: https://github.com/elastic/opentelemetry-demo
[Google Cloud]: https://github.com/GoogleCloudPlatform/opentelemetry-demo
[Grafana Labs]: https://github.com/grafana/opentelemetry-demo
[Guance]: https://github.com/GuanceCloud/opentelemetry-demo
[Honeycomb.io]: https://github.com/honeycombio/opentelemetry-demo
[Instana]: https://github.com/instana/opentelemetry-demo
[Kloudfuse]: https://github.com/kloudfuse/opentelemetry-demo
[Liatrio]: https://github.com/liatrio/opentelemetry-demo
[Logz.io]: https://logz.io/learn/how-to-run-opentelemetry-demo-with-logz-io/
[New Relic]: https://github.com/newrelic/opentelemetry-demo
[OpenSearch]: https://github.com/opensearch-project/opentelemetry-demo
[Oracle]: https://github.com/oracle-quickstart/oci-o11y-solutions/blob/main/knowledge-content/opentelemetry-demo
[Sentry]: https://github.com/getsentry/opentelemetry-demo
[ServiceNow Cloud Observability]: https://docs.lightstep.com/otel/quick-start-operator#send-data-from-the-opentelemetry-demo
[Splunk]: https://github.com/signalfx/opentelemetry-demo
[Sumo Logic]: https://www.sumologic.com/blog/common-opentelemetry-demo-application/
[TelemetryHub]: https://github.com/TelemetryHub/opentelemetry-demo/tree/telemetryhub-backend
[Teletrace]: https://github.com/teletrace/opentelemetry-demo
[Tracetest]: https://github.com/kubeshop/opentelemetry-demo
[Uptrace]: https://github.com/uptrace/uptrace/tree/master/example/opentelemetry-demo
