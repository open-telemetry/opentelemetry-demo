# OpenTelemetry Astronomy Shop Demo with New Relic

![image](./images/newrelic+otel.png)

This repository contains a fork of the OpenTelemetry Astronomy Shop, a microservice-based distributed system intended to illustrate the implementation of OpenTelemetry in a near real-world environment.  It includes customizations for use with the New Relic platform.

## Pre-requisites

Bring a New Relic License Key from your New Relic account.  If you don't have one, you can sign up for a [Free Trial here](https://newrelic.com/signup)!

## Setup

Clone the repo and navigate to the `newrelic/scripts` directory on your machine:

```bash
git clone https://github.com/bpschmitt/opentelemetry-demo && cd opentelemetry-demo/newrelic/scripts
```

## Installation Options

- [Kubernetes](#kubernetes-installation)
- [Docker](./)

## Kubernetes Installation

Run the `install-k8s.sh` script to install the Astronomy Shop Demo into your cluster.  This script uses Helm to perform the install so if you'd rather use `kubectl` and manifests, you can find them [here](../k8s/rendered).  

> **_NOTE:_** You'll be prompted for your New Relic license key so have it ready!

```bash
./install.sh
```
Example output:

```bash
$ ./install-k8s.sh
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

### Cleanup Kubernetes

To uninstall the demo from your cluster, you can use the `cleanup-k8s.sh` script.  This script will uninstall the helm release and delete the `opentelemetry-demo` namespace.

```bash
./cleanup-k8s.sh
```

Example output:
```bash
$ ./cleanup-k8s.sh
Helm release 'otel-demo' found. Uninstalling...
release "otel-demo" uninstalled
Successfully uninstalled 'otel-demo'
Namespace 'opentelemetry-demo' found. Deleting...
namespace "opentelemetry-demo" deleted
```


## Docker Installation

While we recommend running in Kubernetes, the OpenTelemetry Astronomy Shop demo can also run on a Docker machine as well.  Use the `install-docker.sh` script to get up and running quickly.

> **_NOTE:_** You'll be prompted for your New Relic license key so have it ready!

```bash
$ ./install-docker.sh
Please enter your New Relic License Key: <REDACTED>
[+] Running 21/21
 ✔ Container fraud-detection  Started                                                                                                                   16.2s 
 ✔ Container accounting       Started                                                                                                                   16.2s 
 ✔ Container flagd-ui         Started                                                                                                                    7.0s 
 ✔ Container checkout         Started                                                                                                                   16.2s 
 ✔ Container frontend         Started                                                                                                                   16.3s 
 ✔ Container cart             Started                                                                                                                    7.9s 
 ✔ Container image-provider   Started                                                                                                                    7.3s 
 ✔ Container recommendation   Started                                                                                                                    8.5s 
 ✔ Container ad               Started                                                                                                                    7.8s 
 ✔ Container quote            Started                                                                                                                    7.6s 
 ✔ Container load-generator   Started                                                                                                                   16.4s 
 ✔ Container kafka            Healthy                                                                                                                   16.0s 
 ✔ Container valkey-cart      Started                                                                                                                    5.8s 
 ✔ Container payment          Started                                                                                                                    8.0s 
 ✔ Container product-catalog  Started                                                                                                                    7.8s 
 ✔ Container shipping         Started                                                                                                                    7.5s 
 ✔ Container email            Started                                                                                                                    7.3s 
 ✔ Container currency         Started                                                                                                                    7.8s 
 ✔ Container otel-collector   Started                                                                                                                    6.5s 
 ✔ Container flagd            Started                                                                                                                    5.9s 
 ✔ Container frontend-proxy   Started                                                                                                                   15.7s 
 ```



### Cleanup Docker


To uninstall the demo from your machine, you can use the `cleanup-docker.sh` script.  This script will stop and then remove all of the created containers for the demo

```bash
./cleanup-docker.sh
```

Example Output - (Warnings can be ignored):
 ```bash
$ ./cleanup-docker.sh
WARN[0000] The "NEW_RELIC_LICENSE_KEY" variable is not set. Defaulting to a blank string. 
WARN[0000] The "NEW_RELIC_LICENSE_KEY" variable is not set. Defaulting to a blank string. 
[+] Running 22/22
 ✔ Container frontend-proxy    Removed                                                                                                                  10.2s 
 ✔ Container fraud-detection   Removed                                                                                                                  0.6s 
 ✔ Container accounting        Removed                                                                                                                  0.2s 
 ✔ Container load-generator    Removed                                                                                                                  5.4s 
 ✔ Container flagd-ui          Removed                                                                                                                  0.2s 
 ✔ Container frontend          Removed                                                                                                                  0.2s 
 ✔ Container checkout          Removed                                                                                                                  0.2s 
 ✔ Container quote             Removed                                                                                                                  0.3s 
 ✔ Container recommendation    Removed                                                                                                                  10.2s 
 ✔ Container ad                Removed                                                                                                                  0.6s 
 ✔ Container image-provider    Removed                                                                                                                  0.2s 
 ✔ Container shipping          Removed                                                                                                                  10.2s 
 ✔ Container cart              Removed                                                                                                                  0.3s 
 ✔ Container kafka             Removed                                                                                                                  1.3s 
 ✔ Container email             Removed                                                                                                                  0.2s 
 ✔ Container payment           Removed                                                                                                                  0.8s 
 ✔ Container currency          Removed                                                                                                                  10.2s 
 ✔ Container valkey-cart       Removed                                                                                                                  0.2s 
 ✔ Container product-catalog   Removed                                                                                                                  0.1s 
 ✔ Container flagd             Removed                                                                                                                  0.2s 
 ✔ Container otel-collector    Removed                                                                                                                  1.5s 
 ✔ Network opentelemetry-demo  Removed                                                                                                                  0.0s
 ```

### Known Issues with Docker

You may see errors in the OTel Collector logs related to the `dockerstats` receiver.  It appears that this is related to running the demo on a Mac.  More info [here](https://github.com/open-telemetry/opentelemetry-demo/issues/1677)