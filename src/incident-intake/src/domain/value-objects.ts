export type IncidentId = string;
export type EventId = string;
export type IncidentRevision = number;
export type Instant = string;

export interface AlertKey {
  readonly source: string;
  readonly fingerprint: string;
  readonly startedAt: Instant;
}

export interface ServiceReference {
  readonly service: string;
  readonly environment: string | null;
}

export interface TimeRange {
  readonly start: Instant;
  readonly end: Instant;
}

export type Severity = "unknown" | "info" | "warning" | "critical";

export interface Resolution {
  readonly resolvedAt: Instant;
  readonly reason: string;
}
