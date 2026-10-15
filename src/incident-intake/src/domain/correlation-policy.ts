import type { AlertOccurrence } from "./alert-occurrence.js";
import type { IncidentSnapshot } from "./incident.js";
import type { IncidentId } from "./value-objects.js";

export type CorrelationDecision =
  | { readonly kind: "existing"; readonly incidentId: IncidentId }
  | { readonly kind: "new" }
  | { readonly kind: "ambiguous"; readonly candidateIds: readonly IncidentId[] };

export interface CorrelationPolicy {
  correlate(alert: AlertOccurrence, candidates: readonly IncidentSnapshot[]): CorrelationDecision;
}
