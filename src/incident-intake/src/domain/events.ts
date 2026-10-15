import type { AlertKey, EventId, IncidentId, IncidentRevision, Instant, Resolution } from "./value-objects.js";

interface EventMetadata {
  readonly eventId: EventId;
  readonly incidentId: IncidentId;
  readonly incidentRevision: IncidentRevision;
  readonly occurredAt: Instant;
}

export type IncidentDomainEvent = EventMetadata & (
  | { readonly type: "IncidentOpened"; readonly initialAlert: AlertKey }
  | { readonly type: "AlertCorrelatedToIncident"; readonly alert: AlertKey }
  | { readonly type: "IncidentUpdated"; readonly changedAlert: AlertKey }
  | { readonly type: "IncidentResolved"; readonly resolution: Resolution }
);
