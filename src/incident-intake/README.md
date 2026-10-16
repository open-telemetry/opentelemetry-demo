# Incident Intake Service

Goal: turn incoming alerts into reliable requests for investigation.
It doesn't provide the full telemetry context to the investigation event. It just provides the alert info, and necessary context needed for the investigation worker to then request the telemetry information to the applicable services.

## Architecture status

The service provides a local HTTP preview for Grafana webhooks.
It authenticates requests, validates the payload, and maps alerts to
the internal application contract.
Preview mode logs normalized notifications and returns success without
persisting data. Incident processing, deduplication, correlation,
PostgreSQL persistence, outbox delivery, and broker integration are
not implemented yet.

See [WEBHOOK-PREVIEW.md](WEBHOOK-PREVIEW.md) for local setup.

## Bounded context and ownership

Incident Management owns incident identity, alert correlation, severity, and
operational lifecycle. Investigation owns evidence, hypotheses, and reports.
Remediation owns proposed fixes and PR creation. The latter two contexts are
outside this service.

The worker receives incident context and reports investigation summaries through
explicit cross-context contracts. The transport for each direction is undecided:
it could use HTTP APIs, message queues, or a combination. Only Incident Management
writes its incident tables. A summary is a local projection, not the authoritative
report. An investigation finishing does not imply that an incident has recovered.

## Domain vocabulary

| Concept | DDD role | Meaning |
| --- | --- | --- |
| Incident | Aggregate root and entity | Operational problem with identity and revision |
| AlertOccurrence | Child entity | A firing episode, identified by source, fingerprint, and start time |
| AlertKey | Value object | Compound occurrence identity |
| ServiceReference | Value object | Service and environment description |
| TimeRange | Value object | A query window, reserved for future use |
| Resolution | Value object | Time and reason for resolving an incident |
| CorrelationPolicy | Domain service contract | Decides whether an alert belongs to a candidate incident |
| IncidentDomainEvent | Domain event union | Facts produced by aggregate transitions |

The Incident interface is a behavior contract, not an aggregate implementation.
Its snapshot is read-only data for persistence and correlation. Value objects
are structural, read-only contracts; runtime validation, equality, normalization,
and immutability enforcement remain to be implemented. String ID/time aliases do
not validate UUIDs or timestamps. These contracts are a starting vocabulary,
not proof that business invariants are enforced.

## Dependency direction

```text
adapters -> application -> domain
bootstrap -> application (and concrete adapters when implemented)
```

Domain code has no HTTP, database, broker, or framework imports. Application
ports describe dependencies; adapters implement them. Bootstrap is the
composition root and currently requires dependencies supplied by the caller.
No framework or dependency injection container is required.

```text
Grafana request
  -> GrafanaWebhookAdapter (authentication, validation, mapping)
  -> ProcessAlertNotificationUseCase
  -> CorrelationPolicy + Incident behavior
  -> UnitOfWork
       -> incident changes + receipt + integration events in one transaction
  -> durable success response

OutboxDispatcher -> MessagePublisher -> task broker -> investigation worker
Incident context -> transport adapter (TBD) -> worker
Worker summaries -> transport adapter (TBD) -> record summary use case
```

The existing `IncidentApiAdapter` is an optional HTTP adapter placeholder, not a
transport decision. Application ports remain independent of HTTP or messaging.

## Ports and transaction boundaries

- Inbound: process an alert notification, get incident context, record an
  investigation summary. Only the first use-case class is scaffolded; the others
  are contracts for later implementation.
- Outbound: incident repository, notification receipts, summary repository,
  outbox repository, unit of work, message publisher, clock, ID generator.
- Repositories passed to a UnitOfWork callback must share one transaction.
  Incident changes, receipt claims, and outbox appends commit or roll back together.
- `save(incident, expectedRevision)` must reject stale writes. A null expected
  revision means insert only. Persistence must also enforce occurrence uniqueness;
  optimistic locking alone does not prevent concurrent creation of two incidents.
- Receipt claim must be atomic and unique for source + delivery ID. Grafana may
  provide no delivery ID. Do not substitute its notification group key: repeated
  notifications in a group may contain meaningful updates. Occurrence identity
  and transition rules must still provide idempotency.
- Outbox claims need expiring leases and ownership checks using claim tokens.
  Publish before acknowledging. Delivery is at least once, so consumers must
  deduplicate stable event IDs. Retries/backoff and dead-letter handling are pending.
- Worker summary updates use a per-investigation summary revision to reject stale
  updates independently of the incident revision that was investigated.

## Domain events versus integration messages

Internal events express aggregate facts, including alert correlation. The
versioned IncidentIntegrationEventV1 is a separate cross-context contract carrying
an incident ID and revision, not telemetry or a serialized aggregate. This is a
provisional message shape: whether context is fetched separately or delivered
through messages remains undecided. The read port supports a possible retrieval
path without requiring HTTP. Translation, event coalescing, and serialization
are not implemented. One incident revision should normally
produce one externally relevant update even if several internal events occur.

## Policies to decide before implementation

- Correlation keys, time window, ambiguous matches, and missing service identity.
- How to handle resolved-before-firing and out-of-order notifications when source
  payloads provide no reliable per-occurrence update sequence.
- Whether all alerts resolving is enough to resolve an incident or whether a
  separate recovery check or human decision is required.
- Severity mapping and aggregation across correlated alerts.
- What qualifies as a meaningful update and increments the incident revision.
- Alert association/history retention and limits on aggregate size.
- Notification grouping: proposed initial behavior is all-or-nothing processing
  within a transaction; reconsider if groups grow large.
- Transport and delivery contracts for worker context and investigation summaries:
  HTTP, messaging, or a combination; context snapshots versus separate retrieval.
- Authentication, payload limits, external contract shapes, persistence schema, and broker.

The intake emits meaningful incident changes. Investigation decides whether to
start, incorporate an update into existing work, or schedule follow-up. This
service does not manage worker leases or automatically open PRs.

## Development

```sh
npm ci
npm run typecheck
npm run build
```

Build output is in `dist/`. No start command is provided because execution is not
implemented. Before adding behavior, cover duplicate notifications, concurrent
creation, stale updates, correlation ambiguity, resolution ordering, transaction
rollback, and outbox redelivery with meaningful tests.
