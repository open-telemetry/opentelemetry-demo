# Infrastructure components runbook

This runbook covers the shared infrastructure components that the
microservices depend on: **flagd, kafka, valkey-cart, postgresql**.
These are deployed as part of the chart and don't typically have business
logic that needs PRs against — but they can fail.

## flagd (feature flag service)

flagd is the OpenFeature reference implementation that holds feature flag
state for all services. Every service queries it on startup and during
request handling.

**Symptoms of failure**:
- Service startup hangs (services that block on flagd connection)
- Random behavior changes across services (flag values inconsistent)
- 5xx from services that depend on flag-gated code paths

**Triage**:
```
kubectl get pod -l app=flagd
kubectl logs -l app=flagd --tail=50
```

**Common fixes**:
- Pod down → `kubectl rollout restart deployment/flagd`
- ConfigMap malformed → check `kubectl get configmap flagd-config -o yaml`
  for the JSON definition; redeploy via Helm to reset to chart-rendered defaults

## kafka

Kafka is the event-streaming backbone for order events flowing from
checkout → accounting + fraud-detection.

**Symptoms of failure**:
- Consumer lag grows on accounting / fraud-detection
- checkout's post-order publish call returns errors

**Triage**:
```
kubectl get pod -l app=kafka
kubectl exec -it deploy/kafka -- kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --all-groups
```

**Common fixes**:
- Pod restart for transient issues
- Storage volume issues — kafka requires persistent storage
- Consumer-side bugs surface as lag — fix in the consuming service

## valkey-cart (Redis-compatible store)

Backing store for the cart service. Pure key-value workload.

**Symptoms**:
- cart service 5xx
- High memory usage approaching the pod limit

**Triage**:
```
kubectl exec -it deploy/valkey-cart -- redis-cli INFO memory
kubectl exec -it deploy/valkey-cart -- redis-cli DBSIZE
```

**Common fixes**:
- Pod down → restart
- Memory full → check eviction policy (`maxmemory-policy`); bump pod
  memory limit in `chart/values.yaml`

## postgresql

Backing store for accounting service.

**Symptoms**:
- accounting service connection errors
- Slow inserts under load

**Triage**:
```
kubectl exec -it deploy/postgresql -- psql -U postgres -c "select count(*) from pg_stat_activity"
kubectl logs -l app=postgresql --tail=50
```

**Common fixes**:
- Pod restart
- Connection pool exhaustion on caller side → bump pool size in accounting service
- Disk full → resize PVC

## When to NOT open a PR

These infrastructure components live in the chart but their source isn't
in `src/`. They're vendored upstream packages. Don't open PRs against
their internal code — instead:

- Bug in how the service uses the infrastructure → PR against `src/{service}/`
- Capacity issue → bump resources in `chart/values.yaml`
- Configuration change → update the relevant `chart/templates/components/{infra}.yaml` values
