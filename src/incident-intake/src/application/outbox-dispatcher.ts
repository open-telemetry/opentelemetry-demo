import type { Clock, MessagePublisher, OutboxRepository } from "./ports/outbound.js";
import { NotImplementedError } from "./not-implemented-error.js";

export class OutboxDispatcher {
  constructor(
    readonly outbox: OutboxRepository,
    readonly publisher: MessagePublisher,
    readonly clock: Clock,
  ) {}

  async dispatchBatch(): Promise<never> {
    throw new NotImplementedError("OutboxDispatcher: leasing, publication, acknowledgement, retries");
  }
}
