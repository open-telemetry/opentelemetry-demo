# otel-demo on Azure (AKS)

The demo runs on AKS and sends telemetry to Azure Application Insights and
SolarWinds Observability. Code pushed to the `azure` branch under `src/` is built
and rolled out automatically by `.github/workflows/azure-deploy.yml`.

| Resource | Name |
|---|---|
| Resource group | `otel-demo-rg` (centralindia) |
| AKS | `otel-demo-aks` (1 × Standard_D4s_v6, Container Insights on) |
| Container registry | `oteldemo5352cb.azurecr.io` |
| Log Analytics | `otel-demo-logs` (1 GB/day cap) |
| Application Insights | `otel-demo-appi` |
| CI identity | app registration `otel-demo-github-ci` (OIDC, `azure` branch only; AcrPush + AKS Cluster User) |

## Azure resources (Terraform)

Everything in the table above is described in `terraform/`. Terraform's state is in
the storage account `oteldemotfstateca5de3` (resource group `otel-demo-tfstate-rg`).

```bash
cd deploy/azure/terraform
terraform init -backend-config=backend.hcl
terraform plan      # preview; "No changes" means Azure matches the files
terraform apply     # make Azure match the files
```

### Moving to another Azure account

1. `AZURE_CONFIG_DIR=~/.azure-<name> az login`, and keep that `export` in the terminal.
2. Create a state storage account + `tfstate` container in the new subscription (in its
   own resource group), grant yourself "Storage Blob Data Contributor" on it, and put
   its names in `backend.hcl`.
3. In `terraform.tfvars`: set `subscription_id`, pick a new globally unique `acr_name`,
   and delete the `aks_dns_prefix` line.
4. Check the node size has quota: `az vm list-usage -l centralindia -o table`.
5. `terraform init -backend-config=backend.hcl && terraform apply` (~10 min).
6. `terraform output`: copy the four IDs into the `env:` block of
   `.github/workflows/azure-deploy.yml`, and
   `terraform output -raw appinsights_connection_string` into `secrets.env`.
7. Install the demo (below).

`terraform destroy` removes everything it created (the state storage stays).

## Secrets

Never commit them. Put them in `deploy/azure/secrets.env` (git-ignored):

```
APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=...
SOLARWINDS_REGION=ap-01
SOLARWINDS_TOKEN=...
```

## Install / update the demo

```bash
az aks get-credentials -g otel-demo-rg -n otel-demo-aks --file ~/.kube/otel-demo-aks.config
export KUBECONFIG=~/.kube/otel-demo-aks.config

kubectl create namespace otel-demo --dry-run=client -o yaml | kubectl apply -f -
kubectl -n otel-demo create secret generic otel-demo-exporters \
  --from-env-file=deploy/azure/secrets.env --dry-run=client -o yaml | kubectl apply -f -

helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm upgrade --install otel-demo open-telemetry/opentelemetry-demo --version 0.42.1 \
  -n otel-demo -f deploy/azure/values-azure.yaml
```

Needs Helm ≥ 3.14 (the chart does not render on older versions).

`helm upgrade` resets every service to the upstream image. Services deployed by CI
go back to upstream until their next push.

## Chaos: break a service with a code change

1. Commit the bug to a `chaos-azure/*` branch (one small commit per scenario).
2. Merge or cherry-pick it onto `azure` and push. CI builds only the changed
   service, deploys it, and records the commit on the deployment:
   `kubectl -n otel-demo rollout history deployment/<service>`
3. Watch it fail in App Insights, SolarWinds and Container Insights.
4. `git revert` the commit on `azure` and push to recover.

## Cost

Stop the cluster when idle: `az aks stop -g otel-demo-rg -n otel-demo-aks`
(`az aks start ...` to resume). Delete everything: `az group delete -n otel-demo-rg`.
