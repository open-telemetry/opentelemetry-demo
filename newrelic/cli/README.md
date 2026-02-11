# New Relic OpenTelemetry Demo CLI

This CLI tool automates the deployment of the OpenTelemetry Astronomy Shop demo and its integration with New Relic. It supports provisioning New Relic sub-accounts via Terraform, deploying to Kubernetes via Helm, or running locally with Docker Compose.

## Prerequisites

Ensure the following tools are installed based on your target environment for compiling or running locally:

| Target | Required Tools |
| :--- | :--- |
| **All** | **Go** (1.20+) |
| **Kubernetes** | `kubectl`, `helm` |
| **Docker** | `docker` (with Compose V2 support) |
| **Terraform** | `terraform`, `jq`, `curl` |

## Compilation

To compile the project into a single binary for your corresponding to your operating system, run the following command from the `cli/` directory:

**macOS (Apple Silicon / M1 / M2)**
```bash
GOOS=darwin GOARCH=arm64 go build -o onr-otel-cli .
```

**macOS (Intel)**
```bash
GOOS=darwin GOARCH=amd64 go build -o nr-otel-cli .
```

**Linux (AMD64)**
```bash
GOOS=linux GOARCH=amd64 go build -o nr-otel-cli .
```

**Windows**
```bash
GOOS=windows GOARCH=amd64 go build -o nr-otel-cli .
```

### Run the Binary
Ensure the binary has execution permissions (Mac/Linux) and run it:

```bash
chmod +x otel-demo
./otel-demo
```

## General Usage

The CLI supports both an interactive guided mode and a non-interactive batch mode.

### 1. Interactive Mode

Simply run the binary (or use `go run`) without arguments to start the interactive wizard:

```bash
./nr-otel-cli
# OR
go run .

```

The wizard will guide you through selecting an **Action** (Install, Upgrade, Uninstall) and a **Target** (Account, Resources, K8s, Docker), prompting for required credentials as needed.

### 2. Batch Mode

For automation, you can provide the action and target directly:

```bash
./nr-otel-cli <action> <target> [flags]

# OR
go run . <action> <target> [flags]

```

**Valid Actions:** `install`, `upgrade`, `uninstall`.

**Valid Targets:** `account`, `resources`, `k8s`, `docker`.

---

## Configuration Flags

All flags can be passed as command-line arguments (e.g., `--NEW_RELIC_REGION=EU`) or set as environment variables (e.g., `export NEW_RELIC_REGION=EU`).

### Global Flags

* `--NEW_RELIC_REGION`: "US" or "EU" (Default: US).
* `--NEW_RELIC_ENABLE_BROWSER`: Set to "true" to enable Browser Monitoring (K8s/Docker only).

### Deployment Flags (K8s / Docker)

* `--NEW_RELIC_LICENSE_KEY`: Your New Relic License Key (must end in `NRAL`).

### Terraform Account Flags (Target: `account`)

* `--NEW_RELIC_API_KEY`: New Relic User API Key (starts with `NRAK-`).
* `--NEW_RELIC_ACCOUNT_ID`: Your Parent Account ID.
* `--TF_VAR_SUBACCOUNT_NAME`: Name for the new sub-account.
* `--TF_VAR_ADMIN_GROUP_NAME`: Existing group name to grant Admin access.
* `--TF_VAR_READONLY_USER_NAME`: Name for the new read-only user.
* `--TF_VAR_READONLY_USER_EMAIL`: Email for the new read-only user.

### Browser Monitoring Flags

Required if `NEW_RELIC_ENABLE_BROWSER` is true:

* `--BROWSER_LICENSE_KEY`
* `--BROWSER_APPLICATION_ID`
* `--BROWSER_ACCOUNT_ID`
* `--BROWSER_TRUST_KEY`
* `--BROWSER_AGENT_ID`