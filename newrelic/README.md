# OpenTelemetry Astronomy Shop Demo with New Relic

![image](./images/newrelic+otel.png)

This repository contains a fork of the OpenTelemetry Astronomy Shop, a microservice-based distributed system intended to illustrate the implementation of OpenTelemetry in a near real-world environment.  It includes customizations for use with the New Relic platform.

## Pre-requisites

- kubectl
- helm
- terraform
- a K8s cluster
- a New Relic Account and your New Relic license key.  Sign up for a [Free Trial here](https://newrelic.com/signup)!

## Installation

Run the script below to install the Astronomy Shop Demo into your cluster.  You'll be prompted for your New Relic license key so have it ready!

```bash
./install.sh
```
Example output:

```bash
$ ./install.sh
Please enter your New Relic License Key: <REDACTED>
namespace/opentelemetry-demo created
secret/newrelic-license-key created
Release "otel-demo" does not exist. Installing it now.
NAME: otel-demo
LAST DEPLOYED: Fri Mar  7 16:17:51 2025
NAMESPACE: opentelemetry-demo
STATUS: deployed
REVISION: 1
TEST SUITE: None
NOTES:
=======================================================================================


 ██████╗ ████████╗███████╗██╗         ██████╗ ███████╗███╗   ███╗ ██████╗
██╔═══██╗╚══██╔══╝██╔════╝██║         ██╔══██╗██╔════╝████╗ ████║██╔═══██╗
██║   ██║   ██║   █████╗  ██║         ██║  ██║█████╗  ██╔████╔██║██║   ██║
██║   ██║   ██║   ██╔══╝  ██║         ██║  ██║██╔══╝  ██║╚██╔╝██║██║   ██║
╚██████╔╝   ██║   ███████╗███████╗    ██████╔╝███████╗██║ ╚═╝ ██║╚██████╔╝
 ╚═════╝    ╚═╝   ╚══════╝╚══════╝    ╚═════╝ ╚══════╝╚═╝     ╚═╝ ╚═════╝


- All services are available via the Frontend proxy: http://localhost:8080
  by running these commands:
     kubectl --namespace opentelemetry-demo port-forward svc/frontend-proxy 8080:8080

  The following services are available at these paths after the frontend-proxy service is exposed with port forwarding:
  Webstore             http://localhost:8080/
  Jaeger UI            http://localhost:8080/jaeger/ui/
  Grafana              http://localhost:8080/grafana/
  Load Generator UI    http://localhost:8080/loadgen/
  Feature Flags UI     http://localhost:8080/feature/
```

## Cleanup

```bash
./cleanup.sh
```

Example output:
```bash
$ ./cleanup.sh
Helm release 'otel-demo' found. Uninstalling...
release "otel-demo" uninstalled
Successfully uninstalled 'otel-demo'
Namespace 'opentelemetry-demo' found. Deleting...
namespace "opentelemetry-demo" deleted
```