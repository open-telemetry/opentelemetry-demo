import type { ProcessAlertNotificationCommand } from "../../application/contracts.js";
import type { ProcessAlertNotification } from "../../application/ports/inbound.js";
import { NotImplementedError } from "../../application/not-implemented-error.js";

export interface GrafanaWebhookMapper {
  map(payload: unknown, receivedAt: string): ProcessAlertNotificationCommand;
}

export class GrafanaWebhookAdapter {
  constructor(
    readonly intake: ProcessAlertNotification,
    readonly mapper: GrafanaWebhookMapper,
  ) {}

  async handle(_request: unknown): Promise<never> {
    throw new NotImplementedError("GrafanaWebhookAdapter: authentication, validation, mapping, HTTP response");
  }
}
