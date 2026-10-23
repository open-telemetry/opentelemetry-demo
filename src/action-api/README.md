# Action API

The **Action API** is the isolated, security-hardened write gateway and container inspector for the OpenTelemetry Astronomy Shop AI On-Call Engineer.

Per **ONCALL_SPEC §2 and §6**, the Action API is the **only component with access to the Docker socket (`/var/run/docker.sock`)**. The AI agent itself runs completely unprivileged without Docker socket access and with read-only tools.

---

## 1. Security Architecture & Hard Rules

1. **Only write path:** All mutations to container lifecycles, feature flags, or load generator settings must pass through `POST /actions`.
2. **Approval token required:** Mutating (non-dry-run) actions require an HMAC-SHA256 signature generated with `ACTION_API_SECRET` over `{incident_id, action, params, exp}`. Mismatched or expired tokens return `403 Forbidden`.
3. **Emergency Kill Switch:** `POST /killswitch {"engaged": true}` immediately locks all mutating actions, causing them to return `423 Locked`. State persists across container restarts in `/data/killswitch.json`.
4. **Allowlist enforcement:**
   - **Service Restarts:** Allowlisted to 17 demo services (`ad`, `cart`, `checkout`, `currency`, `email`, `frontend`, `image-provider`, `payment`, `product-catalog`, `quote`, `recommendation`, `shipping`, `accounting`, `fraud-detection`, `kafka`, `valkey-cart`, `astronomy-db`).
   - **Protected Services:** Core observability and control plane services (`otel-collector`, `prometheus`, `jaeger`, `opensearch`, `flagd`, `flagd-ui`, `action-api`, `oncall-agent`) can **never** be restarted (rejected with `400 Bad Request`).
   - **Feature Flags:** Restrictive to 20 runbook flags, and only permits transition to the `"off"` / default variant.
5. **No Flag Leakage:** The Action API never returns previous or current flag values to callers or in API responses. The AI agent remains strictly blind to flag configurations.
6. **Rate Limiting:** Maximum 1 mutating action per service per 60 seconds (rejects rapid bursts with `429 Too Many Requests`).
7. **Complete Audit Trail:** Every single request (approved, dry-run, rejected, rate-limited, locked) is written as an immutable JSON line to `/data/audit.jsonl`.

---

## 2. API Endpoints

### Health & Liveness
- `GET /health`: Liveness probe. Returns `{"status": "ok", "service": "action-api"}`.

### Read-Only Inspector
- `GET /containers`: Lists all containers with status, health check status, restart count, OOM killed flags, exit code, CPU%, and memory usage.
- `GET /containers/{name}`: Detailed inspection of a specific container.
- `GET /events?since_minutes=N`: Ring buffer of recent Docker lifecycle events (`start`, `die`, `oom`, `restart`, `kill`, `stop`) merged with actions executed by this API.

### Safety & Controls
- `GET /killswitch`: Returns current killswitch status `{"engaged": bool}`.
- `POST /killswitch`: Sets killswitch status `{"engaged": bool}`.
- `GET /audit?limit=N`: Returns recent audit trail records.

### Actions Gateway
- `POST /actions`:
  ```json
  {
    "action": "restart_service" | "set_feature_flag" | "throttle_load_generator" | "scale_service" | "rollback",
    "params": { ... },
    "incident_id": "INC-1234",
    "approval_token": "<exp>:<hmac-sha256-hex>",
    "dry_run": false
  }
  ```

Supported actions:
- `restart_service`: `{"service": "<service_name>"}`
- `set_feature_flag`: `{"flag": "<flag_name>", "variant": "off"}`
- `throttle_load_generator`: `{"users": <int>, "spawn_rate": <float>}`
- `scale_service`: Returns `{"status": "unsupported", "reason": "Kubernetes only; this deployment is Docker Compose"}`
- `rollback`: `{"action_id": "<uuid>"}`

---

## 3. Local Verification

Run unit tests directly:
```bash
PYTHONPATH=src/action-api pytest src/action-api/tests
```
