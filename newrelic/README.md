# OpenTelemetry Astronomy Shop Demo with New Relic

![image](./images/newrelic+otel.png)

This repository contains a fork of the OpenTelemetry Astronomy Shop, a microservice-based distributed system intended to illustrate the implementation of OpenTelemetry in a near real-world environment.  It includes customizations for use with the New Relic platform.

## Table of Contents

- [Prerequisites](#prerequisites)
  - [Terraform (Optional)](#terraform-optional)
  - [Kubernetes](#kubernetes)
  - [Docker](#docker)

- [Setup](#setup)
- [Installation Options](#installation-options)
  - [Terraform Automation (Optional)](#terraform-automation-optional)
  - [Kubernetes Installation](#kubernetes-installation)
  - [Docker Installation](#docker-installation)
- [Validating the Install](#validating-the-install)
- [Accessing the Flagd UI](#accessing-the-flagd-ui)

## Prerequisites

You'll need a New Relic License Key from your New Relic account. If you don't have an account, you can get one for [free!](https://newrelic.com/signup)

### Terraform (Optional)

If you plan to use the Terraform automation modules to create New Relic resources:

- [Terraform](https://www.terraform.io/downloads) 1.4+
- [jq](https://stedolan.github.io/jq/) (for JSON processing)
- curl (typically pre-installed)
- New Relic User API Key (for managing accounts and resources)

The Terraform modules are completely optional. You can run the demo with just your existing New Relic license key.

### Kubernetes

> **NOTE**: If you are installing into an **OpenShift** cluster, please [complete steps 1 - 5 in the OpenTelemetry Demo helm chart README](https://github.com/open-telemetry/opentelemetry-helm-charts/tree/main/charts/opentelemetry-demo#openshift) prior to installation.

For our testing, we used a [Minikube](https://minikube.sigs.k8s.io/docs/start/) cluster with 4 CPUs and 8GB Memory.  The official demo docs state:

- Kubernetes 1.24+
- 6 GB of free RAM for the application
- Helm 3.14+ (for Helm installation method only)

For more details, see the Kubernetes Deployment docs [here](https://opentelemetry.io/docs/demo/kubernetes-deployment/).

### Docker

For our testing, we used [Docker Desktop](https://www.docker.com/products/docker-desktop/).  The official demo docs state:

- Docker
- [Docker Compose](https://docs.docker.com/compose/install/) v2.0.0+
- Make (option)
- 6 GB of RAM for the application

For more details, see the Docker Deployment docs [here](https://opentelemetry.io/docs/demo/docker-deployment/).

## Setup

Clone the repo.

```bash
git clone https://github.com/newrelic/opentelemetry-demo
```

Navigate to the `opentelemetry-demo/newrelic/scripts` directory on your machine:

```bash
cd opentelemetry-demo/newrelic/scripts
```

## Installation Options

Choose the installation method that best fits your environment:

- **[Terraform (Optional)](#terraform-automation-optional)**: Automate New Relic account setup and/or resource creation
- **[Kubernetes](#kubernetes-installation)**: Deploy to a Kubernetes cluster using Helm
- **[Docker](#docker-installation)**: Run locally with Docker Compose

**Note**: All installation methods require a New Relic license key (this can be generated via [Terraform](#terraform-automation-optional)). You can input it when prompted, or export a `NEW_RELIC_LICENSE_KEY` environment variable to avoid repeated prompts.

## Terraform Automation (Optional)

This repository includes Terraform modules and automated scripts to simplify New Relic account setup and showcase observability best practices. Using these modules is completely optional - the demo works perfectly fine with your existing New Relic license key.

### Why Use Terraform?

The Terraform modules demonstrate how to:
- **Automate account setup** - Programmatically create dedicated sub-accounts for isolated demo environments
- **Showcase New Relic capabilities** - Implement SLOs, alerts, dashboards, teams, and other observability features
- **Follow Observability as Code best practices** - Manage observability resources alongside your application infrastructure
- **Scale observability practices** - Apply consistent patterns across multiple services and environments

### What's Included

Two independent Terraform modules are provided in the [`terraform/`](./terraform/) directory:

1. **[`nr_account`](./terraform/nr_account/)** - Automates creation of New Relic sub-accounts and license keys
   - Creates isolated environments for demos or testing
   - Generates the license key needed for installation
   - Configurable region (US or EU)
   - Grants access to specified admin groups

2. **[`nr_resources`](./terraform/nr_resources/)** - Creates New Relic resources to showcase platform capabilities
   - Currently includes Service Level Objectives (SLOs)
   - Future additions: alerts, dashboards, teams, scorecards, and more
   - Demonstrates programmatic resource management as code

### Quick Start with Terraform

Automated scripts handle the Terraform workflow for you:

```bash
# Navigate to the scripts directory
cd opentelemetry-demo/newrelic/scripts

# 1. (Optional) Create a sub-account and license key
./install-nr-account.sh

# 2. Export the license key and deploy the demo
export NEW_RELIC_LICENSE_KEY=$(cd ../terraform/nr_account && terraform output -raw license_key)
./install-k8s.sh  # or ./install-docker.sh (see below)

# 3. Wait 2-5 minutes for data to flow to New Relic

# 4. Create New Relic resources to showcase platform capabilities
./install-nr-resources.sh
```

### Environment Variables

You can set environment variables to avoid interactive prompts. If not set, the scripts will prompt for values.

#### install-nr-account.sh

| Variable | Required | Description |
|----------|----------|-------------|
| `TF_VAR_newrelic_api_key` | Yes | New Relic User API Key |
| `TF_VAR_newrelic_parent_account_id` | Yes | Parent account ID for sub-account creation |
| `TF_VAR_newrelic_region` | No | New Relic region (US or EU, default: US) |
| `TF_VAR_subaccount_name` | Yes | Name for the new sub-account |
| `TF_VAR_authentication_domain_name` | No | Authentication domain name (default: Default) |
| `TF_VAR_admin_group_name` | Yes | Admin group name (must exist in New Relic) |
| `TF_VAR_admin_role_name` | No | Admin role name (default: all_product_admin) |
| `TF_AUTO_APPROVE` | No | Set to `true` to skip Terraform confirmation prompts |

#### install-nr-resources.sh

| Variable | Required | Description |
|----------|----------|-------------|
| `TF_VAR_newrelic_api_key` | Yes | New Relic User API Key |
| `TF_VAR_account_id` | Yes | New Relic Account ID where resources will be created |
| `TF_AUTO_APPROVE` | No | Set to `true` to skip Terraform confirmation prompts |

#### cleanup-nr-account.sh & cleanup-nr-resources.sh

| Variable | Required | Description |
|----------|----------|-------------|
| `TF_AUTO_APPROVE` | No | Set to `true` to skip Terraform confirmation prompts |

**Example with environment variables:**

```bash
export TF_VAR_newrelic_api_key="your-api-key"
export TF_VAR_newrelic_parent_account_id="12345"
export TF_VAR_subaccount_name="OpenTelemetry Demo"
export TF_VAR_admin_group_name="Admin"
export TF_AUTO_APPROVE=true

./install-nr-account.sh
```

### Manual Terraform Workflow

If you prefer to run Terraform commands directly, please see the individual modules under `terraform/` directory.

### Cleanup

To remove Terraform-created resources:

```bash
cd opentelemetry-demo/newrelic/scripts
./cleanup-nr-resources.sh  # Remove New Relic resources (SLOs, etc.)
./cleanup-nr-account.sh     # Remove sub-account and license key
```

## Kubernetes Installation

Run the `install-k8s.sh` script to install the Astronomy Shop Demo into your cluster.  This script uses `helm` to perform the install so if you'd rather use `kubectl` and manifests, you can find them [here](./k8s/rendered).

```bash
./install-k8s.sh
```

### Environment Variables

You can set environment variables to avoid interactive prompts. If not set, the script will prompt for values.

| Variable | Required | Description |
|----------|----------|-------------|
| `NEW_RELIC_LICENSE_KEY` | Yes | New Relic Ingest License Key |
| `IS_OPENSHIFT_CLUSTER` | No | Set to `y` for OpenShift clusters, `n` otherwise (default: n) |

**Example:**

```bash
export NEW_RELIC_LICENSE_KEY="your-license-key"
export IS_OPENSHIFT_CLUSTER="n"
./install-k8s.sh
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

> **_NOTE:_** It can take anywhere from 2 - 5 minutes for Pods to start up and telemetry to flow through the OTel Collector and on to New Relic.  Please have patience.  If you want to check on the status of the OTel collector, you can run `kubectl logs deployment/otel-collector -n opentelemetry-demo`

### Customize Kubernetes installation
You can apply changes to the deployed OpenTelemetry Demo by modifying any values in `newrelic/k8s/helm/opentelemetry-demo.yaml`. See supported values in the official OpenTelemetry Demo Helm Chart [here](https://github.com/open-telemetry/opentelemetry-helm-charts/tree/main/charts/opentelemetry-demo#chart-parameters).

After you save changes, you can re-run `install-k8s.sh` to apply changes and redeploy the modified components.

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

```bash
./install-docker.sh
```

### Environment Variables

You can set environment variables to avoid interactive prompts. If not set, the script will prompt for values.

| Variable | Required | Description |
|----------|----------|-------------|
| `NEW_RELIC_LICENSE_KEY` | Yes | New Relic Ingest License Key |

**Example:**

```bash
export NEW_RELIC_LICENSE_KEY="your-license-key"
./install-docker.sh
```

Example output:

```bash
$ ./install-docker.sh
[+] Running 21/21
 ✔ Container fraud-detection  Started      16.2s 
 ✔ Container accounting       Started      16.2s 
 ✔ Container flagd-ui         Started       7.0s 
 ✔ Container checkout         Started      16.2s 
 ✔ Container frontend         Started      16.3s 
 ✔ Container cart             Started       7.9s 
 ✔ Container image-provider   Started       7.3s 
 ✔ Container recommendation   Started       8.5s 
 ✔ Container ad               Started       7.8s 
 ✔ Container quote            Started       7.6s 
 ✔ Container load-generator   Started      16.4s 
 ✔ Container kafka            Healthy      16.0s 
 ✔ Container valkey-cart      Started       5.8s 
 ✔ Container payment          Started       8.0s 
 ✔ Container product-catalog  Started       7.8s 
 ✔ Container shipping         Started       7.5s 
 ✔ Container email            Started       7.3s 
 ✔ Container currency         Started       7.8s 
 ✔ Container otel-collector   Started       6.5s 
 ✔ Container flagd            Started       5.9s 
 ✔ Container frontend-proxy   Started      15.7s 
 ```

> **_NOTE:_** It can take anywhere from 2 - 5 minutes for data to flow through the OTel Collector and become visible in New Relic once the containers are running.  Please have patience.  If you want to check on the status of the OTel collector, you can run `docker logs -f $(docker ps | grep otel-collector | awk '{print $1}')`.  Use `CTRL + C` to exit.

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
 ✔ Container frontend-proxy    Removed      10.2s 
 ✔ Container fraud-detection   Removed      0.6s 
 ✔ Container accounting        Removed      0.2s 
 ✔ Container load-generator    Removed      5.4s 
 ✔ Container flagd-ui          Removed      0.2s 
 ✔ Container frontend          Removed      0.2s 
 ✔ Container checkout          Removed      0.2s 
 ✔ Container quote             Removed      0.3s 
 ✔ Container recommendation    Removed      10.2s 
 ✔ Container ad                Removed      0.6s 
 ✔ Container image-provider    Removed      0.2s 
 ✔ Container shipping          Removed      10.2s 
 ✔ Container cart              Removed      0.3s 
 ✔ Container kafka             Removed      1.3s 
 ✔ Container email             Removed      0.2s 
 ✔ Container payment           Removed      0.8s 
 ✔ Container currency          Removed      10.2s 
 ✔ Container valkey-cart       Removed      0.2s 
 ✔ Container product-catalog   Removed      0.1s 
 ✔ Container flagd             Removed      0.2s 
 ✔ Container otel-collector    Removed      1.5s 
 ✔ Network opentelemetry-demo  Removed      0.0s
 ```

### Known Issues with Docker

You may see errors in the OTel Collector logs related to the `dockerstats` receiver.  It appears that this is related to running the demo on a Mac.  More info [here.](https://github.com/open-telemetry/opentelemetry-demo/issues/1677)

## Validating the Install

Check the container logs for the OTel Collector to ensure there aren't any errors related to data collection or shipping telemetry to the New Relic platform. After a few minutes, you should see a list of the Astronomy Shop services in the `Services - OpenTelemetry` menu under the `All Entities` view.  

![all_otel_entities](./images/all_otel_entities.png)

If you click on the `Frontend` service, you should see data populated in the Summary page.

![frontend_service](./images/frontend_service.png)

## Accessing the FlagD UI

You can enable / disable various feature flags provided by the community using the Flagd UI.  In order to access the Flagd UI, you'll need to set up port-forwarding to your local machine.  Here's an example command you can use:

```bash
kubectl -n opentelemetry-demo port-forward svc/frontend-proxy 8080:8080
```

If port `8080` is already in use on your local machine, use a different port like `9999` or another that you know will be open.  For example:

```bash
kubectl -n opentelemetry-demo port-forward svc/frontend-proxy 9999:8080
```

After setting up port forwarding, you can access the Flagd UI at [http://localhost:4000/feature](http://localhost:4000/feature).

![flagdui](./images/flagdui.png)
