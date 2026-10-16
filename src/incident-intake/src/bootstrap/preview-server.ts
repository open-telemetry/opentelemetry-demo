import { DefaultGrafanaWebhookMapper, GrafanaWebhookAdapter } from "../adapters/inbound/grafana-webhook.js";
import { createWebhookServer } from "../adapters/inbound/http-server.js";

const port = Number(process.env.PORT ?? 8081);
if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error("Invalid PORT");
const token = process.env.INTAKE_WEBHOOK_TOKEN;
if (!token) throw new Error("Set INTAKE_WEBHOOK_TOKEN before starting preview mode");

const adapter = new GrafanaWebhookAdapter({
  async execute(command) {
    console.log("PREVIEW ONLY: normalized notification; no data persisted");
    console.log(JSON.stringify(command, null, 2));
    return { incidents: [] };
  },
}, new DefaultGrafanaWebhookMapper(process.env.GRAFANA_SOURCE ?? "grafana-demo"));

const server = createWebhookServer(adapter, { token, preview: true });
server.listen(port, "0.0.0.0", () => {
  console.log(`PREVIEW ONLY: listening on ${port}; authentication required; no persistence`);
});
for (const signal of ["SIGINT", "SIGTERM"] as const) {
  process.on(signal, () => server.close());
}
