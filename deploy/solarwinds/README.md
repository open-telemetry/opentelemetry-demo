# SolarWinds alerts → Slack

Terraform creates a Slack notification and three alerts in SolarWinds Observability,
all scoped to the otel-demo (the account also holds other environments).

| Alert | Fires when | Severity |
|---|---|---|
| otel-demo: pod not ready | a pod in `otel-demo` is not ready for 10 min (crash loop, failing probe) | CRITICAL |
| otel-demo: service error rate | a demo service's traced error rate ≥ 90% for 10 min | WARNING |
| otel-demo: slow requests | average HTTP server duration ≥ 1 s for 10 min | WARNING |

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
