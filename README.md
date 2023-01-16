# ![otel-photo](./docs/img/opentelemetry-logo-nav.png) OpenTelemetry Demo

[![Slack](https://img.shields.io/badge/slack-@cncf/otel/demo-brightgreen.svg?logo=slack)](https://cloud-native.slack.com/archives/C03B4CWV4DA)
[![Version](https://img.shields.io/github/v/release/open-telemetry/opentelemetry-demo?color=blueviolet)](https://github.com/open-telemetry/opentelemetry-demo/releases)
[![Commits](https://img.shields.io/github/commits-since/open-telemetry/opentelemetry-demo/latest?color=ff69b4&include_prereleases)](https://github.com/open-telemetry/opentelemetry-demo/graphs/commit-activity)
[![Downloads](https://img.shields.io/docker/pulls/otel/demo)](https://hub.docker.com/r/otel/demo)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg?color=red)](https://github.com/open-telemetry/opentelemetry-demo/blob/main/LICENSE)

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

If you'd like to extend this demo or maintain a fork of it, please read our
[fork guidance](./docs/forking.md).

## Quick start

You can be up and running with the demo in a few minutes. Check out the docs for
your preferred deployment method:

- [Docker](./docs/docker_deployment.md)
- [Kubernetes](./docs/kubernetes_deployment.md)

## Documentation

We have detailed documentation available in the [docs](./docs/) folder. If you're
curious about a specific feature the docs [README](./docs/README.md) can point
you in the right direction.

## Demos featuring the Astronomy Shop

We welcome any vendor to fork the project to demonstrate their services and
adding a link below. The community is committed to maintaining the project and
keeping it up to date for you.

|                                                                                                                   |                                                                                                 |                                                                                              |
|-------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------|
| [AlibabaCloud LogService](https://github.com/aliyun-sls/opentelemetry-demo)                                       | [Dynatrace](https://www.dynatrace.com/news/blog/opentelemetry-demo-application-with-dynatrace/) | [New Relic](https://github.com/newrelic/opentelemetry-demo)                                  |
| [AppDynamics](https://www.appdynamics.com/blog/cloud/how-to-observe-opentelemetry-demo-app-in-appdynamics-cloud/) | [Grafana Labs](https://github.com/grafana/opentelemetry-demo)                                   | [Splunk](https://github.com/signalfx/opentelemetry-demo)                                     |
| [Aspecto](https://github.com/aspecto-io/opentelemetry-demo)                                                       | [Helios](https://otelsandbox.gethelios.dev)                                                     | [Sumo Logic](https://github.com/SumoLogic/opentelemetry-demo)                                |
| [Coralogix](https://coralogix.com/blog/configure-otel-demo-send-telemetry-data-coralogix)                         | [Honeycomb.io](https://github.com/honeycombio/opentelemetry-demo)                               | [TelemetryHub](https://github.com/TelemetryHub/opentelemetry-demo/tree/telemetryhub-backend) |
| [Datadog](https://github.com/DataDog/opentelemetry-demo)                                                          | [Lightstep](https://github.com/lightstep/opentelemetry-demo)                                    | [Uptrace](https://github.com/uptrace/uptrace/tree/master/example/opentelemetry-demo)         |

## Contributing

To get involved with the project see our [CONTRIBUTING](CONTRIBUTING.md)
documentation. Our [SIG Calls](CONTRIBUTING.md#join-a-sig-call) are Mondays at
8:15 AM PST and anyone is welcome.

## Project leadership

[Maintainers](https://github.com/open-telemetry/community/blob/main/community-membership.md#maintainer)
([@open-telemetry/demo-maintainers](https://github.com/orgs/open-telemetry/teams/demo-maintainers)):

- [Austin Parker](https://github.com/austinlparker), Lightstep
- [Carter Socha](https://github.com/cartersocha), Lightstep
- [Juliano Costa](https://github.com/julianocosta89), Dynatrace
- [Pierre Tessier](https://github.com/puckpuck), Honeycomb

[Approvers](https://github.com/open-telemetry/community/blob/main/community-membership.md#approver)
([@open-telemetry/demo-approvers](https://github.com/orgs/open-telemetry/teams/demo-approvers)):

- [Michael Maxwell](https://github.com/mic-max), Microsoft
- [Mikko Viitanen](https://github.com/mviitane), Dynatrace
- [Penghan Wang](https://github.com/wph95), AppDynamics
- [Reiley Yang](https://github.com/reyang), Microsoft
- [Ziqi Zhao](https://github.com/fatsheep9146), Alibaba

Emeritus:

- [Morgan McLean](https://github.com/mtwo)

### Thanks to all the people who have contributed

[![contributors](https://contributors-img.web.app/image?repo=open-telemetry/opentelemetry-demo)](https://github.com/open-telemetry/opentelemetry-demo/graphs/contributors)
