import type { OutboxRepository, TransactionContext, UnitOfWork } from "../../application/ports/outbound.js";

export abstract class PostgresUnitOfWork implements UnitOfWork {
  abstract run<T>(operation: (transaction: TransactionContext) => Promise<T>): Promise<T>;
}

export abstract class PostgresOutboxRepository implements OutboxRepository {
  abstract append(...args: Parameters<OutboxRepository["append"]>): ReturnType<OutboxRepository["append"]>;
  abstract claimBatch(...args: Parameters<OutboxRepository["claimBatch"]>): ReturnType<OutboxRepository["claimBatch"]>;
  abstract markPublished(...args: Parameters<OutboxRepository["markPublished"]>): ReturnType<OutboxRepository["markPublished"]>;
}
