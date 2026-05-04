# Getting Started — Sureops Sample Environment

Welcome. This guide walks you through what got provisioned for you, how to
exercise the demo, and how to interpret what sureops shows you.

## What's running

Coord (sureops's per-customer provisioner) set up:

| Resource | URL / location |
|---|---|
| Your sample app frontend | `https://{your-slug}.sample-uat.sureops.ai` |
| Failure flag UI | `https://{your-slug}.sample-uat.sureops.ai/feature` |
| Your Grafana | `https://{your-slug}-grafana.sample-uat.sureops.ai` |
| Your ArgoCD | `https://{your-slug}-argocd.sample-uat.sureops.ai` |
| Your Slack channel | `#uat-{your-slug}-incidents` (in the sureops-private-beta workspace) |
| This repository | `https://github.com/sureops-private-beta/uat-{your-slug}-otel-demo` |

## How to drive a demo

1. **Browse the storefront** — open the frontend URL, click around. You
   should see a working ecommerce site with products, cart, checkout, etc.
2. **Open `/feature`** — you'll see a list of feature flags. Each is a
   real failure scenario in real service code.
3. **Flip a flag** (e.g., `paymentFailure`) — within ~3 seconds, the
   relevant service will start failing.
4. **Watch your sureops dashboard** — within ~30 seconds, an incident
   will open. Sureops's diagnosis agent will start triaging.
5. **Wait for the fix-PR agent** — it'll open a draft PR against this
   repository proposing a code-level fix.
6. **Review and merge** the PR. CI rebuilds the affected service, ArgoCD
   redeploys. Incident closes.

## Understanding the telemetry

Every service emits:
- **Traces** to your per-customer Tempo (queryable via Grafana → Explore → Tempo)
- **Metrics** to your per-customer Prometheus (queryable via Grafana → Explore → Prometheus)
- **Logs** to your per-customer Loki (queryable via Grafana → Explore → Loki)

These are tenanted by your customer slug (`X-Scope-OrgID` header). You
only see your own data.

## Where to get help

- **Slack**: `#uat-{your-slug}-incidents` — sureops staff respond here
- **Issues**: open an issue on this repository if you find a bug in the
  sample app or sureops's behavior
- **Architecture deep-dive**: `docs/architecture.md`
