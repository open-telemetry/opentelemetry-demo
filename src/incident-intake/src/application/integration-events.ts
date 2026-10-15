import type { EventId, IncidentId, IncidentRevision, Instant } from "../domain/value-objects.js";

export interface IncidentIntegrationEventV1 {
  readonly schemaVersion: 1;
  readonly eventId: EventId;
  readonly type: "incident.opened" | "incident.updated" | "incident.resolved";
  readonly incidentId: IncidentId;
  readonly incidentRevision: IncidentRevision;
  readonly occurredAt: Instant;
}
