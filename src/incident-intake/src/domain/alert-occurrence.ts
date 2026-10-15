import type { AlertKey, Instant, ServiceReference, Severity } from "./value-objects.js";

export type AlertStatus = "firing" | "resolved";

export interface AlertOccurrence {
  readonly key: AlertKey;
  readonly status: AlertStatus;
  readonly affectedService: ServiceReference | null;
  readonly summary: string;
  readonly severity: Severity;
  readonly resolvedAt: Instant | null;
  readonly labels: Readonly<Record<string, string>>;
  readonly annotations: Readonly<Record<string, string>>;
}
