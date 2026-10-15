import type { IncidentId } from "../../domain/value-objects.js";
import type { IncidentContext, InvestigationSummaryUpdate, ProcessAlertNotificationCommand, ProcessAlertNotificationResult } from "../contracts.js";

export interface ProcessAlertNotification {
  execute(command: ProcessAlertNotificationCommand): Promise<ProcessAlertNotificationResult>;
}

export interface GetIncidentContext {
  execute(incidentId: IncidentId): Promise<IncidentContext | null>;
}

export interface RecordInvestigationSummary {
  execute(update: InvestigationSummaryUpdate): Promise<void>;
}
