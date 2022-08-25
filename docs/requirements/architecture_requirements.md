# Demo Architecture

## Summary

The OpenTelemetry Community Demo application is intended to be a 'showcase' for
OpenTelemetry API, SDK, and tools in a production-lite cloud native
application. The overall goal of this application is not only to provide a
canonical 'demo' of OpenTelemetry components, but also to act as a framework for
further customization by end-users, vendors, and other stakeholders.

### Requirements

- [Application Requirements](./application_requirements.md)
- [OpenTelemetry Requirements](./opentelemetry_requirements.md)
- [System Requirements](./system_requirements.md)

### Application Goals

- Provide developers with a robust sample application they can use in learning
OpenTelemetry instrumentation.
- Provide observability vendors with a single,
well-supported, demo platform that they can further customize (or simply use
OOB).
- Provide the OpenTelemetry community with a living artifact that
demonstrates the features and capabilities of OTel APIs, SDKs, and tools.
- Provide OpenTelemetry maintainers and WGs a platform to demonstrate new
features/concepts 'in the wild'.

The following is a general description of the logical components of the demo
application.

## Main Application

The bulk of the demo app is a self-contained
microservice-based application that does some useful 'real-world' work, such as
an eCommerce site. This application is composed of multiple services that
communicate with each other over gRPC and HTTP and runs on Kubernetes (or
Docker, locally).

Each service shall be instrumented with OpenTelemetry for traces, metrics, and
logs (as applicable/available).

Each service should be 'swappable' with a service that performs the same
business logic, implementing the same gRPC endpoints, but written in a different
language/implementation. For the initial implementation of the demo, we should
focus on adding as many missing languages as possible by swapping out existing
services with implementations in un-represented languages. For future versions
we will look to add more distinct language options per service.

Each service should communicate with a feature flag service in order to
enable/disable 'faults' that can be used to illustrate how telemetry helps solve
problems in distributed applications.

A PHP service should be added to the main application as an 'admin service'. A
Database should be added to enable CRUD functionality on the Product Catalog.

The 'shippingservice' should be reimplemented in Rust.

The 'currencyservice' should be reimplemented in C++.

The 'emailservice' should be reimplemented in Ruby.

For future iterations, the 'frontend' service can be extended with a mobile
application written in Swift.

## Feature Flag Component

This component should consist of one (or more) services
that provides a simple feature flag configuration utility for the main
application. It is made up of a browser-based client/admin interface and a
backend service or services. The role of the client is to allow an operator to
visualize the available feature flags and toggle their state. The server should
provide a catalog of feature flags that main application services can register
with and interrogate for their current status and targeting rules.

The feature flag component should be implemented as an Erlang+Elixir/Phoenix
service. The catalog of feature flags should be stored in a Database.

## Orchestration and Deployment

All services should run on Kubernetes. The
OpenTelemetry Collector should be deployed via the OpenTelemetry Operator, and
run in a sidecar + gateway mode. Telemetry from each pod should be routed from
agents to a gateway, and the gateway should export telemetry by default to an
open-source trace + metrics visualizer.

For local/non-kubernetes deployment, the Collector should be deployed via
compose file and monitor not only traces/metrics from applications, but also the
docker containers via dockerstatsreceiver.

A design goal of this project is to include a CI/CD pipeline for self-deployment
into cloud environments. This could be skipped for local development.
