import type { AlertOccurrence } from "./alert-occurrence.js";
import type { IncidentDomainEvent } from "./events.js";
import type { AlertKey, IncidentId, IncidentRevision, Instant, Resolution, Severity } from "./value-objects.js";

export interface IncidentSnapshot {
  readonly id: IncidentId;
  readonly revision: IncidentRevision;
  readonly status: "open" | "resolved";
  readonly summary: string;
  readonly severity: Severity;
  readonly alerts: readonly AlertOccurrence[];
  readonly createdAt: Instant;
  readonly updatedAt: Instant;
  readonly resolution: Resolution | null;
}

export interface Incident {
  snapshot(): IncidentSnapshot;
  attachAlert(alert: AlertOccurrence, occurredAt: Instant): void;
  recordAlertResolution(key: AlertKey, resolvedAt: Instant, receivedAt: Instant): void;
  resolve(resolution: Resolution): void;
  pendingEvents(): readonly IncidentDomainEvent[];
}
