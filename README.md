# Sureops Sample App — OpenTelemetry Demo

> This is the **sureops template fork** of the OpenTelemetry Astronomy Shop
> ([upstream](https://github.com/open-telemetry/opentelemetry-demo)).
> It serves as the seed for per-customer demo environments in sureops's
> private beta. Each customer gets their own fork of THIS repository,
> with their own ArgoCD pipeline, image builds, and ownership.

## What you're looking at

If you're a sureops customer, this is **your sample environment's source
code**. Every microservice in the storefront — payment, cart, recommendation,
ad, etc. — lives in `src/`. The Helm chart that deploys them lives in
`chart/`. Sureops's diagnosis and fix-PR agents read this repository
(via github-mcp) when investigating incidents in your environment.

## Repository layout

```
src/                       # 14 microservices (Go, Python, .NET, Java, Rust, JS, Ruby, ...)
chart/                     # Helm chart deployed by ArgoCD into your namespace
  values.yaml              # base config
  values-sureops.yaml      # sureops-flavored overrides (collector → sureops Tempo/Loki)
  values-customer.yaml     # per-customer stamping (your slug, org_id, env)
.sureops/                  # agent contract — service map + runbooks
  service-map.yaml         # routes "incident on service X" → "src/X, runbook Y, chart values Z"
  runbooks/{service}.md    # production-style runbook per service
.github/workflows/         # CI: image builds, chart lint, sync from sureops template
docs/                      # human-facing docs (getting started, architecture)
```

## What sureops does for you

When something breaks in your environment:

1. Telemetry from your services (traces, metrics, logs) flows to sureops's
   multi-tenant Tempo / Prometheus / Loki via the OTel Collector deployed
   by `chart/`
2. Alerts fire to sureops's incident webhook
3. Sureops opens an incident on your behalf
4. The diagnosis agent reads `.sureops/service-map.yaml` to find the right
   source code + runbook for the affected service
5. The fix-PR agent (when applicable) opens a draft PR against this
   repository proposing a fix
6. You review the PR like any other code change. Merge → CI builds new
   image → ArgoCD redeploys → incident closes

## Failure injection

This sample app has built-in failure scenarios you can flip via feature
flags at `https://{your-slug}.sample-uat.sureops.ai/feature`. Use these
to test how sureops handles different incident types in your environment.

Failure flags are real: each one corresponds to a code branch in the
relevant service. The sureops agent that responds to the resulting
incident sees the same telemetry it would see in a real production
outage and proposes the same kind of fix.

## Contributing

- **Code changes** (`src/`): customer-owned. Open a PR; merge with normal
  code-review process.
- **Chart changes** (`chart/`): require sureops staff approval (CODEOWNERS).
  Helps catch deploy-impacting changes.
- **Sureops contract** (`.sureops/`): also require sureops staff approval.
  These files are how sureops's agents navigate your code.

For the full architecture, see `docs/architecture.md`.

For getting started, see `docs/sureops-getting-started.md`.

For sureops support, use the Slack channel created at provisioning time
(`#uat-{your-slug}-incidents`).

---

## Upstream attribution

This is a fork of [`open-telemetry/opentelemetry-demo`](https://github.com/open-telemetry/opentelemetry-demo) (Apache 2.0).
The Astronomy Shop demo was created by the OpenTelemetry community as the
canonical reference application for vendor-neutral observability tooling.

This sureops fork adds:
- A vendored Helm chart at `chart/` (from `open-telemetry/opentelemetry-helm-charts`)
  with sureops-specific overrides
- The `.sureops/` agent contract files
- CI workflows for image builds + chart lint + template sync
- Removal of the chart's bundled Jaeger / Grafana / Prometheus / OpenSearch
  (sureops provides multi-tenant equivalents)
