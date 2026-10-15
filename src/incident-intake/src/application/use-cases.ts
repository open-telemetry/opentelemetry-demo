import type { CorrelationPolicy } from "../domain/correlation-policy.js";
import type { ProcessAlertNotificationCommand, ProcessAlertNotificationResult } from "./contracts.js";
import type { ProcessAlertNotification } from "./ports/inbound.js";
import type { Clock, IdGenerator, UnitOfWork } from "./ports/outbound.js";
import { NotImplementedError } from "./not-implemented-error.js";

export interface IntakeDependencies {
  readonly unitOfWork: UnitOfWork;
  readonly correlationPolicy: CorrelationPolicy;
  readonly clock: Clock;
  readonly ids: IdGenerator;
}

export class ProcessAlertNotificationUseCase implements ProcessAlertNotification {
  constructor(readonly dependencies: IntakeDependencies) {}

  async execute(_command: ProcessAlertNotificationCommand): Promise<ProcessAlertNotificationResult> {
    throw new NotImplementedError("ProcessAlertNotificationUseCase");
  }
}
