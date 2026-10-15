import type { GetIncidentContext, RecordInvestigationSummary } from "../../application/ports/inbound.js";
import { NotImplementedError } from "../../application/not-implemented-error.js";

// TODO: TBD. maybe not by API but consumption from message broker.
export class IncidentApiAdapter {
  constructor(
    readonly getContext: GetIncidentContext,
    readonly recordSummary: RecordInvestigationSummary,
  ) {}

  async handle(_request: unknown): Promise<never> {
    throw new NotImplementedError("IncidentApiAdapter: incident reads and investigation summary updates");
  }
}
