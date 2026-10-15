import type { AlertOccurrence } from "../domain/alert-occurrence.js";
import type { IncidentId, IncidentRevision, Instant } from "../domain/value-objects.js";

export interface ProcessAlertNotificationCommand {
  readonly source: string;
  readonly deliveryId: string | null;
  readonly receivedAt: Instant;
  readonly alerts: readonly AlertOccurrence[];
}

export interface ProcessAlertNotificationResult {
  readonly incidents: readonly {
    readonly incidentId: IncidentId;
    readonly revision: IncidentRevision;
    readonly outcome: "created" | "updated" | "unchanged";
  }[];
}

export interface IncidentContext {
  readonly incidentId: IncidentId;
  readonly revision: IncidentRevision;
  readonly status: "open" | "resolved";
  readonly summary: string;
  readonly alerts: readonly AlertOccurrence[];
}

export interface InvestigationSummaryUpdate {
  readonly incidentId: IncidentId;
  readonly investigationId: string;
  readonly summaryRevision: number;
  readonly investigatedIncidentRevision: IncidentRevision;
  readonly status: "pending" | "running" | "completed" | "inconclusive" | "failed";
  readonly reportReference: string | null;
  readonly pullRequestUrl: string | null;
}
