# Architecture — Sureops Sample Environment

## The 3-tier fork chain

```
upstream:    open-telemetry/opentelemetry-demo
                       ↓ fork (one-time, manual; monthly upstream-sync PR)
template:    sureops-private-beta/sample-app-otel-demo
                       ↓ coord forks at provision time per customer
customer:    sureops-private-beta/uat-{slug}-otel-demo  ← THIS repository
```

Your fork pulls weekly updates from the sureops template via the
`customer-sync.yml` workflow. The template pulls monthly updates from
upstream OpenTelemetry Demo via `upstream-sync.yml` (in the template,
gated by sureops staff review).

## Deployment

ArgoCD watches THIS repository's `chart/` directory and syncs to your
Kubernetes namespace (`org-{slug}`). On every commit to `main` that
touches `chart/`, ArgoCD picks up the change within ~3 minutes.

## Image builds

When you (or sureops's fix-PR agent) commit to `src/{service}/`, the
`build-images.yml` workflow:

1. Detects which services changed
2. Builds each one's Dockerfile and pushes to GHCR at
   `ghcr.io/sureops-private-beta/uat-{slug}-otel-demo/{service}:{sha}`
3. Bumps the corresponding `chart/values.yaml` `components.{service}.image.tag`
4. Commits the bump back to `main` with `[skip ci]`
5. ArgoCD picks up the chart change and redeploys

## Telemetry routing

```
Service emits OTLP
        ↓
chart/'s OTel Collector (in your namespace, deployed by Helm)
        ↓
  Stamps customer.slug + deployment.environment as resource attrs
        ↓
  Routes:
    Traces  → sureops shared Tempo  (X-Scope-OrgID = your slug)
    Logs    → sureops shared Loki   (X-Scope-OrgID = your slug)
    Metrics → /metrics on :9464 (per-customer Prometheus scrapes this)
```

## Observability you can reach

Your Grafana org has datasources pre-provisioned for:
- Tempo (traces)
- Prometheus (metrics)
- Loki (logs)

ArgoCD shows your sample app's deployment status. If something's out of
sync (e.g., your last commit hasn't been picked up yet), you'll see it
there.

## Sureops integration

Sureops has 4 in-cluster MCP servers running in your namespace:
- **k8s-mcp** — read-only access to your namespace (pods, logs, events,
  deployments). RBAC scoped to the namespace.
- **grafana-mcp** — query metrics + traces + logs via Grafana
- **argocd-mcp** — query ArgoCD application status
- **github-mcp** — read this repository (for the fix-PR agent)

Sureops's agents use these MCPs to investigate incidents.

## Failure injection (flagd)

`flagd` is the OpenFeature reference implementation. It serves feature
flag state to all services in your namespace. The `flagd-ui` component
exposes a web UI at `/feature` for flipping flags. Flags are defined
in `chart/flagd/demo.flagd.json`.

**Behind the scenes**: Flipping a flag updates the runtime ConfigMap
that flagd watches. Your services receive the updated value within a
few seconds without any redeploy.

The failure-mode mappings (which flag breaks which service, how, and
how to fix) are sureops-internal — they live in the template fork's
`.sureops-internal/` directory and are deliberately not synced into
this customer fork. This is by design: it lets sureops's diagnosis
agents respond to flag-induced failures as if they were real production
bugs, which is exactly the demo loop we want.
