import type { ProcessAlertNotificationCommand, ProcessAlertNotificationResult } from "../../application/contracts.js";
import type { ProcessAlertNotification } from "../../application/ports/inbound.js";

export class InvalidWebhookError extends Error {}

export interface GrafanaWebhookMapper {
  map(payload: unknown, receivedAt: string): ProcessAlertNotificationCommand;
}

function firstNonEmpty(...values: unknown[]): string | null {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }

  return null;
}

function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new InvalidWebhookError("Expected an object");
  }
  return value as Record<string, unknown>;
}

function requiredString(value: unknown, field: string): string {
  if (typeof value !== "string" || !value.trim()) {
    throw new InvalidWebhookError(`Invalid ${field}`);
  }
  return value;
}

function instant(value: unknown, field: string): string {
  const text = requiredString(value, field);
  if (!Number.isFinite(Date.parse(text))) throw new InvalidWebhookError(`Invalid ${field}`);
  return new Date(text).toISOString();
}

function strings(value: unknown): Record<string, string> {
  if (value === undefined) return {};
  const record = object(value);
  for (const item of Object.values(record)) {
    if (typeof item !== "string") throw new InvalidWebhookError("Labels and annotations must contain strings");
  }
  return { ...record } as Record<string, string>;
}

export class DefaultGrafanaWebhookMapper implements GrafanaWebhookMapper {
  constructor(readonly source: string) {
    requiredString(source, "source");
  }

  map(payload: unknown, receivedAt: string): ProcessAlertNotificationCommand {
    const notification = object(payload);
    if (!Array.isArray(notification.alerts) || notification.alerts.length === 0) {
      throw new InvalidWebhookError("Expected a non-empty alerts array");
    }
    return {
      source: this.source,
      deliveryId: null,
      receivedAt: instant(receivedAt, "receivedAt"),
      alerts: notification.alerts.map((value) => {
        const alert = object(value);
        const status = alert.status;
        if (status !== "firing" && status !== "resolved") {
          throw new InvalidWebhookError("Invalid alert status");
        }
        const labels = strings(alert.labels);
        const annotations = strings(alert.annotations);
        const startedAt = instant(alert.startsAt, "startsAt");
        const resolvedAt = status === "resolved" ? instant(alert.endsAt, "endsAt") : null;
        if (resolvedAt !== null && resolvedAt < startedAt) {
          throw new InvalidWebhookError("endsAt precedes startsAt");
        }
        const service = firstNonEmpty(labels["service.name"], labels.service_name, labels.service,);
        const environment = firstNonEmpty(labels["deployment.environment.name"], labels.deployment_environment_name, labels.environment,);
        const severity = firstNonEmpty(labels.severity)?.toLowerCase();
        const summary = firstNonEmpty( annotations.summary, labels.alertname,) ?? "Grafana alert";
        return {
          key: {
            source: this.source,
            fingerprint: requiredString(alert.fingerprint, "fingerprint"),
            startedAt,
          },
          status,
          affectedService: service ? { service, environment } : null,
          summary: summary,
          severity: severity === "critical" || severity === "warning" || severity === "info" ? severity : "unknown",
          resolvedAt,
          labels,
          annotations,
        };
      }),
    };
  }
}

export class GrafanaWebhookAdapter {
  constructor(
    readonly intake: ProcessAlertNotification,
    readonly mapper: GrafanaWebhookMapper,
  ) {}

  async handle(payload: unknown, receivedAt = new Date().toISOString()): Promise<ProcessAlertNotificationResult> {
    const command = this.mapper.map(payload, receivedAt);
    return this.intake.execute(command);
  }
}
