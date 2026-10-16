# Local Grafana webhook preview

Receives Grafana notifications, authenticates and validates them, and logs both
original and normalized payloads. Preview mode does not save alerts, create
incidents, or schedule investigations.

## First-time setup

Requires Node.js 22. From `src/incident-intake`, create the local configuration:

```powershell
Copy-Item .env.incidents.example .env.incidents
```

Generate a token in PowerShell:

```powershell
[guid]::NewGuid().ToString('N')
```

Paste the result into `INTAKE_WEBHOOK_TOKEN` in `.env.incidents`. Do not commit
that file. Create it before starting Grafana: Compose loads the same token into
Grafana, and the provisioned `incident-intake` contact point sends it automatically
as a Bearer credential. No manual token entry in Grafana is needed.

If the token changes, restart Intake and recreate the Grafana container using
your usual Compose files and any local certificate overrides. A container restart
alone does not reload its environment variables.

## Run

From `src/incident-intake`:

```powershell
npm ci
npm run build
npm run preview
```

Keep the terminal open. Intake currently runs locally, not through Docker Compose.
After TypeScript changes, stop it with Ctrl+C, rebuild, and run preview again.

The endpoint is `POST http://localhost:8081/webhooks/grafana`. Grafana running in
Docker Desktop uses `http://host.docker.internal:8081/webhooks/grafana`.

## Test

In Grafana, open **Alerting > Contact points > incident-intake > Test** and send a
notification. The Intake terminal should show the original Grafana payload,
followed by the normalized notification.

The contact point test sends a synthetic alert. To test a real rule, ensure its
notifications route to `incident-intake` and inspect the same terminal.
Acknowledged notifications are not saved; use this receiver only for local tests.

```powershell
npm run typecheck
npm test
```

## Troubleshooting

| Result | Check |
| --- | --- |
| Connection refused | Intake is running and port `8081` is reachable from Grafana. |
| 401 Unauthorized | Both processes loaded the same token; recreate Grafana after environment changes. |
| 400 Bad Request | The body is valid JSON and each alert has valid required fields. |
| 415 Unsupported Media Type | The request uses `Content-Type: application/json`. |
| 413 Payload Too Large | The request body does not exceed 1 MiB. |
| 500 Internal Server Error | Inspect the Intake terminal for the processing error. |

## Current scope

`http-server.ts` handles HTTP and authentication. `grafana-webhook.ts` validates
and maps the payload, then delegates to the application port. The preview
bootstrap injects a processor that only logs notifications.

Labels and annotations are retained, but the normalized model does not preserve
all Grafana fields, such as query values and rule links. Duplicate notifications
are not deduplicated yet. Persistence, incident lifecycle, correlation, outbox,
and broker integration remain unimplemented.
