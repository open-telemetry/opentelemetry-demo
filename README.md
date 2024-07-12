## New Relic’s Fork of the OpenTelemetry Astronomy Shop

Welcome to New Relic’s fork of the [OpenTelemetry Astronomy Shop](https://opentelemetry.io/ecosystem/demo/)!
This app is a microservice-based distributed system intended to illustrate the
implementation of OpenTelemetry in a near real-world environment. To view the
original repo README, scroll down or click [this link](https://github.com/newrelic/opentelemetry-demo/tree/main?tab=readme-ov-file#-opentelemetry-demo).

After you follow our [quick start instructions]() to deploy the app, check out
[this section]() on how to navigate your data in your New Relic account! 

### Modifications
Please note the following modifications to our fork:
* The helm values file has been modified to avoid breaking upstream changes
* The .env file contains New Relic-specific environment variables so you can quickly
ship the data to your account

### Quick start
Get started quickly by running the app according to your deployment method preference.

Requirements: A New Relic account – [sign up for a free account](https://newrelic.com/signup) if you need one

#### Docker
To run our fork of the app locally using Docker, follow these steps:
1. Clone the repo:
```
git clone https://github.com/newrelic/opentelemetry-demo.git
```
2. Navigate to the repo directory:
```
cd opentelemetry-demo
```
3. Export your [account license key](https://one.newrelic.com/launcher/api-keys-ui.api-keys-launcher?_gl=1*r26ze0*_gcl_au*NjkxMjc4NDcyLjE3MTU2NDM4OTg.*_ga*NjYzMTg1ODUwLjE3MTU2NDM4OTg.*_ga_R5EF3MCG7B*MTcxOTQ1MzE4Ni4xNS4xLjE3MTk0NTMyOTQuNTYuMS40OTYzNDkyMzk.)
(make sure to replace `your_license_key` with your license key):
```
export NEW_RELIC_LICENSE_KEY=your_license_key
```
4. Build and run the app:
```
docker compose up
```
5. Head to your account to view the data
6. To stop the app: `control + c`

#### Kubernetes
[Check out these steps](https://github.com/newrelic/opentelemetry-demo/blob/main/docs/kubernetes_deployment.md). 

### Navigate OTLP data in New Relic
The Demo comes with a number of problem scenarios that you can enable via 
a [feature flag](https://opentelemetry.io/docs/demo/feature-flags/); please 
note that some of these are currently still under testing on our end. 

For this example, we've enabled the feature flag for `productcatalogservice`,
which generates an error for `GetProduct` requests with the product ID: 
OLJCESPC7Z.

If you would like to follow along, navigate to src > flagd > demo.flagd.json,
and on line 11, change the value for `defaultVariant` to `on`. Save the file,
and restart the app. 

Wait a few minutes for the load generator to generate new data; you will pretty
quickly see that the error rates for a couple services have increased. First, go
to the `productcatalogservice` entity in your New Relic account and click on `Errors 
inbox`:

<img width="1401" alt="demo-productcatalogservice-01" src="https://github.com/user-attachments/assets/0105da4b-67d0-4ffe-96d7-fc34b163e6d5">

(In case you are wondering why the Error rate chart next to the Error count chart
appears empty, click on the `...` and select `View query`. You'll see that
this chart is querying for HTTP status code 500. Since this entity isn't 
reporting any 500s, this chart is empty.)

Select the error group `oteldemo.ProductCatalogService/GetProduct`, which will open up 
the error group summary and confirm that the feature flag was enabled:

<img width="1460" alt="demo-productcatalogservice02" src="https://github.com/user-attachments/assets/818f7340-340b-4489-961e-849653520d86">

(Note that there are no logs for this service at this time; per this [
table](https://opentelemetry.io/docs/demo/telemetry-features/log-coverage/), logs have not yet been 
added for `productcatalogservice`.)

Scroll down to `Attributes`, and you can see the attribute `app.product.id` with 
the value `OLJCESPC7Z` was captured:

<img width="1453" alt="demo-productcatalogservice03" src="https://github.com/user-attachments/assets/c4149479-9274-4e20-abb6-1c1db97819d6">

This in itself is not particularly interesting; head on over to the `checkoutservice`
entity and click on `Errors inbox`. You'll see an error group named 
`oteldemo.CheckoutService/PlaceOrder`, with the message `failed to prepare order: 
failed to get product #"OLJCESPC7Z"`:

<img width="1404" alt="demo-checkoutservice01" src="https://github.com/user-attachments/assets/a08c1ca3-376a-48b1-b154-095925668663">

Click on the blue icon under `Distributed Trace`:

<img width="1471" alt="demo-checkoutservice02" src="https://github.com/user-attachments/assets/2c0b69b2-a227-4d64-884c-93a17690dbc9">

You'll see a distributed trace that includes an entity map, showing you how the
error you enabled with the feature flag affected upstream services:

<img width="1333" alt="demo-checkoutservice03" src="https://github.com/user-attachments/assets/d21365d7-4fb3-4ecc-9719-9fb503f2b476">

Click on the "Errors" dropdown menu and select the `checkoutservice` span named
`oteldemo.CheckoutService/PlaceOrder`:

<img width="954" alt="demo-checkoutservice04" src="https://github.com/user-attachments/assets/54402a1e-c6b8-41fe-9c59-bdff62952d24">

On the right-hand panel, click on `View span events` to view more details about
the span event that was captured:

<img width="1330" alt="demo-checkoutservice-05" src="https://github.com/user-attachments/assets/06a29ac2-9492-4a0e-8f58-63d4f48c51b9">

<img width="1468" alt="demo-checkoutservice06" src="https://github.com/user-attachments/assets/dbf7100a-c831-4392-8c8e-ac19e4d95c97">

Since this is a contrived issue, there isn't a lot of particularly useful information 
to view, but it does demonstrate how the error metrics captured are early indicators of these issues
and how they can affect the performance and reliability of your services. Using New Relic
can help you quickly resolve issues by uncovering the root cause through correlated logs and traces,
giving you detailed insights into what happened during a given problem. 

### Roadmap
Similar to how the Astronomy Shop is under active development, we are also actively
developing and maintaining our fork. Here are a few things we have are working on, or
have planned for the near future:
* [Demo scenario feature flags](https://opentelemetry.io/docs/demo/feature-flags/) are in testing
* Support for OTel-sourced Kubernetes infrastructure metrics in New Relic
* add NR instrumentation for recommendationservice to demonstrate interoperability between our language agents and OpenTelemetry
instrumentation

Have a suggestion, or running into problems with our fork? Please let us know by
[opening an issue](https://github.com/newrelic/opentelemetry-demo/issues/new/choose)!

### Contributors
* [Brad Schmitt](https://github.com/bpschmitt)
* [Daniel Kim](https://github.com/lazyplatypus)
* [Krzysztof Spikowski](https://github.com/greenszpila)

-----------

<!-- markdownlint-disable-next-line -->
# <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" alt="OTel logo" width="45"> OpenTelemetry Demo

[![Slack](https://img.shields.io/badge/slack-@cncf/otel/demo-brightgreen.svg?logo=slack)](https://cloud-native.slack.com/archives/C03B4CWV4DA)
[![Version](https://img.shields.io/github/v/release/open-telemetry/opentelemetry-demo?color=blueviolet)](https://github.com/open-telemetry/opentelemetry-demo/releases)
[![Commits](https://img.shields.io/github/commits-since/open-telemetry/opentelemetry-demo/latest?color=ff69b4&include_prereleases)](https://github.com/open-telemetry/opentelemetry-demo/graphs/commit-activity)
[![Downloads](https://img.shields.io/docker/pulls/otel/demo)](https://hub.docker.com/r/otel/demo)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg?color=red)](https://github.com/open-telemetry/opentelemetry-demo/blob/main/LICENSE)
[![Integration Tests](https://github.com/open-telemetry/opentelemetry-demo/actions/workflows/run-integration-tests.yml/badge.svg)](https://github.com/open-telemetry/opentelemetry-demo/actions/workflows/run-integration-tests.yml)

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

|                                         |                             |                                                                |
|-----------------------------------------|-----------------------------|----------------------------------------------------------------|
| [AlibabaCloud LogService][AlibabaCloud] | [Elastic][Elastic]          | [New Relic][NewRelic]                                          |
| [AppDynamics][AppDynamics]              | [Google Cloud][GoogleCloud] | [OpenSearch][OpenSearch]                                       |
| [Aspecto][Aspecto]                      | [Grafana Labs][GrafanaLabs] | [Sentry][Sentry]                                               |
| [Axiom][Axiom]                          | [Guance][Guance]            | [ServiceNow Cloud Observability][ServiceNowCloudObservability] |
| [Axoflow][Axoflow]                      | [Helios][Helios]            | [Splunk][Splunk]                                               |
| [Azure Data Explorer][Azure]            | [Honeycomb.io][Honeycombio] | [Sumo Logic][SumoLogic]                                        |
| [Coralogix][Coralogix]                  | [Instana][Instana]          | [TelemetryHub][TelemetryHub]                                   |
| [Dash0][Dash0]                          | [Kloudfuse][Kloudfuse]      | [Teletrace][Teletrace]                                         |
| [Datadog][Datadog]                      | [Liatrio][Liatrio]          | [Tracetest][Tracetest]                                         |
| [Dynatrace][Dynatrace]                  | [Logz.io][Logzio]           | [Uptrace][Uptrace]                                             |

## Contributing

To get involved with the project see our [CONTRIBUTING](CONTRIBUTING.md)
documentation. Our [SIG Calls](CONTRIBUTING.md#join-a-sig-call) are every other
Monday at 8:30 AM PST and anyone is welcome.

## Project leadership

[Maintainers](https://github.com/open-telemetry/community/blob/main/community-membership.md#maintainer)
([@open-telemetry/demo-maintainers](https://github.com/orgs/open-telemetry/teams/demo-maintainers)):

- [Austin Parker](https://github.com/austinlparker), Honeycomb
- [Juliano Costa](https://github.com/julianocosta89), Datadog
- [Mikko Viitanen](https://github.com/mviitane), Dynatrace
- [Pierre Tessier](https://github.com/puckpuck), Honeycomb

[Approvers](https://github.com/open-telemetry/community/blob/main/community-membership.md#approver)
([@open-telemetry/demo-approvers](https://github.com/orgs/open-telemetry/teams/demo-approvers)):

- [Cedric Ziel](https://github.com/cedricziel) Grafana Labs
- [Penghan Wang](https://github.com/wph95), AppDynamics
- [Reiley Yang](https://github.com/reyang), Microsoft
- [Ziqi Zhao](https://github.com/fatsheep9146), Alibaba

Emeritus:

- [Carter Socha](https://github.com/cartersocha)
- [Michael Maxwell](https://github.com/mic-max)
- [Morgan McLean](https://github.com/mtwo)

### Thanks to all the people who have contributed

[![contributors](https://contributors-img.web.app/image?repo=open-telemetry/opentelemetry-demo)](https://github.com/open-telemetry/opentelemetry-demo/graphs/contributors)

[docs]: https://opentelemetry.io/docs/demo/

<!-- Links for Demos featuring the Astronomy Shop section -->

[AlibabaCloud]: https://github.com/aliyun-sls/opentelemetry-demo
[AppDynamics]: https://www.appdynamics.com/blog/cloud/how-to-observe-opentelemetry-demo-app-in-appdynamics-cloud/
[Aspecto]: https://github.com/aspecto-io/opentelemetry-demo
[Axiom]: https://play.axiom.co/axiom-play-qf1k/dashboards/otel.traces.otel-demo-traces
[Axoflow]: https://axoflow.com/opentelemetry-support-in-more-detail-in-axosyslog-and-syslog-ng/
[Azure]: https://github.com/Azure/Azure-kusto-opentelemetry-demo
[Coralogix]: https://coralogix.com/blog/configure-otel-demo-send-telemetry-data-coralogix
[Dash0]: https://github.com/dash0hq/opentelemetry-demo
[Datadog]: https://docs.datadoghq.com/opentelemetry/guide/otel_demo_to_datadog
[Dynatrace]: https://www.dynatrace.com/news/blog/opentelemetry-demo-application-with-dynatrace/
[Elastic]: https://github.com/elastic/opentelemetry-demo
[GoogleCloud]: https://github.com/GoogleCloudPlatform/opentelemetry-demo
[GrafanaLabs]: https://github.com/grafana/opentelemetry-demo
[Guance]: https://github.com/GuanceCloud/opentelemetry-demo
[Helios]: https://otelsandbox.gethelios.dev
[Honeycombio]: https://github.com/honeycombio/opentelemetry-demo
[Instana]: https://github.com/instana/opentelemetry-demo
[Kloudfuse]: https://github.com/kloudfuse/opentelemetry-demo
[Liatrio]: https://github.com/liatrio/opentelemetry-demo
[Logzio]: https://logz.io/learn/how-to-run-opentelemetry-demo-with-logz-io/
[NewRelic]: https://github.com/newrelic/opentelemetry-demo
[OpenSearch]: https://github.com/opensearch-project/opentelemetry-demo
[Sentry]: https://github.com/getsentry/opentelemetry-demo
[ServiceNowCloudObservability]: https://docs.lightstep.com/otel/quick-start-operator#send-data-from-the-opentelemetry-demo
[Splunk]: https://github.com/signalfx/opentelemetry-demo
[SumoLogic]: https://www.sumologic.com/blog/common-opentelemetry-demo-application/
[TelemetryHub]: https://github.com/TelemetryHub/opentelemetry-demo/tree/telemetryhub-backend
[Teletrace]: https://github.com/teletrace/opentelemetry-demo
[Tracetest]: https://github.com/kubeshop/opentelemetry-demo
[Uptrace]: https://github.com/uptrace/uptrace/tree/master/example/opentelemetry-demo
