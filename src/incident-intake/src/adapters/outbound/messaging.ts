import type { MessagePublisher } from "../../application/ports/outbound.js";
import type { IncidentIntegrationEventV1 } from "../../application/integration-events.js";

export abstract class BrokerMessagePublisher implements MessagePublisher {
  abstract publish(event: IncidentIntegrationEventV1): Promise<void>;
}
