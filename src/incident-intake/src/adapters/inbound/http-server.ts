import { createServer } from "node:http";
import { timingSafeEqual } from "node:crypto";
import { GrafanaWebhookAdapter, InvalidWebhookError } from "./grafana-webhook.js";

export interface WebhookServerOptions {
  readonly token: string;
  readonly preview?: boolean;
}

export function createWebhookServer(adapter: GrafanaWebhookAdapter, options: WebhookServerOptions) {
  if (!options.token) throw new Error("A webhook token is required");
  const expected = Buffer.from(`Bearer ${options.token}`);
  return createServer(async (request, response) => {
    const send = (status: number, body: unknown) => {
      response.writeHead(status, { "Content-Type": "application/json" });
      response.end(JSON.stringify(body));
    };
    if (request.url !== "/webhooks/grafana") {
      send(404, { error: "Not found" });
      return;
    }
    if (request.method !== "POST") {
      response.setHeader("Allow", "POST");
      send(405, { error: "Method not allowed" });
      return;
    }
    const actual = Buffer.from(request.headers.authorization ?? "");
    if (actual.length !== expected.length || !timingSafeEqual(actual, expected)) {
      send(401, { error: "Unauthorized" });
      return;
    }
    if (request.headers["content-type"]?.split(";")[0]?.trim().toLowerCase() !== "application/json") {
      send(415, { error: "Expected application/json" });
      return;
    }
    try {
      const chunks: Buffer[] = [];
      let size = 0;
      for await (const chunk of request) {
        const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
        size += buffer.length;
        if (size > 1024 * 1024) {
          send(413, { error: "Payload too large" });
          return;
        }
        chunks.push(buffer);
      }
      let payload: unknown;
      try {
        payload = JSON.parse(Buffer.concat(chunks).toString("utf8"));
      } catch {
        send(400, { error: "Invalid JSON" });
        return;
      }
      // To be deleted: log the raw payload for debugging purposes
      if (options.preview) {
        console.log("PREVIEW ONLY: original Grafana notification; before normalization");
        console.log(JSON.stringify(payload, null, 2));
      }
      const result = await adapter.handle(payload);
      send(200, options.preview ? { mode: "preview", persisted: false, result } : result);
    } catch (error) {
      if (response.destroyed || response.headersSent) return;
      if (error instanceof InvalidWebhookError) {
        send(400, { error: error.message });
      } else {
        console.error("Webhook processing failed", error);
        send(500, { error: "Processing failed" });
      }
    }
  });
}
