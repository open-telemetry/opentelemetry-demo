# New Relic Configuration

For scenarios where the demo is deployed to a
[Kubernetes cluster via Helm](https://github.com/newrelic/opentelemetry-demo/blob/main/docs/kubernetes_deployment.md),
we provide a number of New Relic configurations that may be helpful. These include:

- Workloads
- Service Levels
- Alert Policies

## Terraform

The [New Relic Terraform Provider](https://registry.terraform.io/providers/newrelic/newrelic/latest/docs)
is used to automate the creation of these entities in New Relic.

## Prerequisites

### Install Terraform

[Install Terraform](https://learn.hashicorp.com/tutorials/terraform/install-cli?_ga=2.188018664.1544580744.1674157852-1046607839.1671584818).

### Configure the Provider

Configure environment variables by adding the following to ~/.bash_profile
(if using bash shell) or ~/.zshrc (on Mac OS Catalina):

```console
export NEW_RELIC_API_KEY="<your New Relic User API key>"
export NEW_RELIC_REGION="US"
```

### Initialize Your Terraform Setup

Navigate to the newrelic-config folder then run the following command to
initialize your Terrform setup:

```console
terraform init
```

### Manage Your Terraform State

If you're using Terraform to apply the New Relic configuration to multiple
accounts, you'll need to create a separate workspaces in Terraform to do so.

For example, to create separate workspaces for dev and staging, navigate to the
newrelic-config folder then run the following command:

```console
terraform workspace new dev
terraform workspace new staging
```

Then if you want to apply the configuration in the staging environment, using
the following command first:

```console
terraform workspace select staging
```

## Apply the Configuration

Navigate to the newrelic-config folder then run the following command to create
the workloads, service levels, and alert policies in your account:

```console
terraform apply -var="account_id=<YOUR ACCOUNT ID>" -var="cluster_name=otel-community-demo" -var="apm_app_name=currencyservice-apm"
```

Substitute the name of the Kubernetes (K8s) cluster and New Relic Account ID where
your demo is running, and the name of the service which is monitored with the
New Relic APM agent, rather than OpenTelemetry.

## Configuration Details

### Workloads

[Workloads](https://docs.newrelic.com/docs/new-relic-solutions/new-relic-one/workloads/workloads-isolate-resolve-incidents-faster/)
provide the ability to group and monitor a set of related entities, providing
aggregated health and activity data from frontend to backend services across
your entire stack.

We configure two workloads as part of the OpenTelemetry demo:

1) Open Telemetry Demo - All Entities: This workload includes all entities
   deployed to the demo cluster.
2) Open Telemetry Demo - Services: This workload includes all APM and OTel
   instrumented services deployed to the demo cluster.

## Service Levels

[Service Levels](https://docs.newrelic.com/docs/service-level-management/intro-slm/)
are used to measure the performance of a service from the end user (or client
application) point of view.

We configure two service levels as part of the OpenTelemetry demo:

1) AdService Service Level: This service level measures the proportion of
   successful requests processed by the AdService.
2) CartService Service Level: This service level measures the proportion of
   successful requests processed by the CartService.

## Alert Policies

In New Relic, you setup alerts for your telemetry data by configuring
[alert conditions](https://docs.newrelic.com/docs/alerts-applied-intelligence/applied-intelligence/incident-intelligence/basic-alerting-concepts/),
which define what will constitute a violation and trigger an incident. Alert
policies are then used to group one or more alert conditions.

We configure the following alert policies as part of the OpenTelemetry demo:

1) OpenTelemetry Service Health: includes conditions to monitor the error rate
   of both APM and OTel-instrumented services.
2) OpenTelemetry Infrastructure Health: includes conditions to monitor the
   health of the Kubernetes cluster and underlying hosts.
