import type { AlertOccurrence } from "../../domain/alert-occurrence.js";
import type { Incident, IncidentSnapshot } from "../../domain/incident.js";
import type { EventId, IncidentId, IncidentRevision, Instant } from "../../domain/value-objects.js";
import type { InvestigationSummaryUpdate } from "../contracts.js";
import type { IncidentIntegrationEventV1 } from "../integration-events.js";

export interface IncidentRepository {
  findById(id: IncidentId): Promise<Incident | null>;
  findCorrelationCandidates(alert: AlertOccurrence): Promise<readonly IncidentSnapshot[]>;
  save(incident: Incident, expectedRevision: IncidentRevision | null): Promise<void>;
}

export interface NotificationReceiptRepository {
  claim(source: string, deliveryId: string): Promise<"new" | "duplicate">;
}

export interface InvestigationSummaryRepository {
  saveIfNewer(summary: InvestigationSummaryUpdate): Promise<void>;
}

export interface OutboxRecord {
  readonly event: IncidentIntegrationEventV1;
  readonly claimToken: string;
}

export interface OutboxRepository {
  append(events: readonly IncidentIntegrationEventV1[]): Promise<void>;
  claimBatch(limit: number, leaseUntil: Instant): Promise<readonly OutboxRecord[]>;
  markPublished(eventId: EventId, claimToken: string): Promise<void>;
}

export interface TransactionContext {
  readonly incidents: IncidentRepository;
  readonly receipts: NotificationReceiptRepository;
  readonly investigationSummaries: InvestigationSummaryRepository;
  readonly outbox: Pick<OutboxRepository, "append">;
}

export interface UnitOfWork {
  run<T>(operation: (transaction: TransactionContext) => Promise<T>): Promise<T>;
}

export interface MessagePublisher {
  publish(event: IncidentIntegrationEventV1): Promise<void>;
}

export interface Clock {
  now(): Instant;
}

export interface IdGenerator {
  nextIncidentId(): IncidentId;
  nextEventId(): EventId;
}
