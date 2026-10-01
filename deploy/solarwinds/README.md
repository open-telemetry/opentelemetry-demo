# SolarWinds alerts → Slack

Terraform creates a Slack notification and 13 alerts in SolarWinds Observability,
modelled on the playground's SigNoz alert set. All are scoped to this cluster
(`k8s.cluster.name = otel-demo-aks`, stamped by the collector) or to the demo's
services, because the account also holds other environments.

| Alert | Fires when | Severity |
|---|---|---|
| High Application Error Rate | one endpoint of a demo service fails ≥ 90% of requests for 10 min | WARNING |
| High Application Latency | an endpoint's average duration ≥ 0.5 s for 10 min | WARNING |
| Service Stopped Reporting | a demo service sends no traces for 10 min (crashed or down) | CRITICAL |
| Pod CrashLoopBackOff | a container is in CrashLoopBackOff for 5 min | CRITICAL |
| Pod OOM Killed | a container's last restart was an OOMKill | CRITICAL |
| Pod Memory Exhaustion (>90% Limit) | a container uses > 90% of its memory limit for 5 min (valkey-cart and astronomy-db excluded: they always do) | WARNING |
| Pod High CPU Usage (>1 CPU) | a pod averages > 1 core for 5 min | WARNING |
| Pod Pending (>5m) | a pod stays Pending for 5 min | WARNING |
| Pod Not Ready | a pod is not ready for 10 min | CRITICAL |
| Node Not Ready | a node is not Ready for 5 min | CRITICAL |
| Node High CPU (>80%) | a node's CPU is > 80% busy for 10 min | WARNING |
| Node High Memory (>85%) | a node's memory is > 85% used for 10 min | WARNING |
| Node Disk Pressure (>85%) | a node filesystem is > 85% full for 10 min | WARNING |

There is no "node not reachable" alert: it would fire on every `demo-stop`.

Some of these need optional collector metrics and the `k8s.cluster.name` tag, enabled
in `deploy/azure/values-azure.yaml` (`opentelemetry-collector.config.receivers` and
`processors.resource`), plus read access to the kubelet's `/pods` endpoint
(`clusterRole.rules`).

A crashed service cannot report its own errors; it shows up as "stopped reporting",
and as failures on the endpoints that call it (e.g. frontend `/api/checkout`).

Thresholds and the list of watched services are in `terraform/variables.tf`.

## Secrets

`secrets.env` (git-ignored):

```
SWO_API_TOKEN=<Full Access API token — not the ingestion token>
TF_VAR_slack_webhook_url=https://hooks.slack.com/services/...
```

## Apply

```bash
cd deploy/solarwinds/terraform
export AZURE_CONFIG_DIR=~/.azure-otel-demo   # state is in the Azure storage account
set -a; . ../secrets.env; set +a
terraform init -backend-config=backend.hcl
terraform plan
terraform apply
```

## Switching to another SolarWinds account

1. Put the new account's Full Access token in `secrets.env` (and a new Slack webhook if the channel changes).
2. In `terraform/terraform.tfvars`, set `swo_region` to the new account's region
   (`my.<region>.cloud.solarwinds.com`).
3. In `terraform/backend.hcl`, change `key` (e.g. `solarwinds-<account>.tfstate`) so the
   old account's state is kept separate.
4. `terraform init -reconfigure -backend-config=backend.hcl && terraform apply`

To remove the alerts from the old account first, run `terraform destroy` before step 1.

The new account needs the demo's data before alerts can fire: point the collector at it
by updating `SOLARWINDS_REGION` / `SOLARWINDS_TOKEN` (ingestion token) in
`deploy/azure/secrets.env` and re-creating the `otel-demo-exporters` secret
(see `deploy/azure/README.md`).
