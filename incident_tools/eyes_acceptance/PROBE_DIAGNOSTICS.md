# Diagnose a failed model probe

A successful curl call and a failed Eyes preflight do not expose the same error detail. The existing Router suppresses provider exceptions and the existing preflight reports MODEL_PROBE_FAILED. This standalone diagnostic observes the same Router request/response boundary without editing its source or changing the production workflow.

Run inside the same Ubuntu shell and repository as Eyes, with the same environment key:

```zsh
python3 -B -m incident_tools.eyes_acceptance.diagnose \
  --config /tmp/eyes-operator/eyes.toml
```

This sends the exact readiness messages through the configured Router and backend. It makes at most one attempt per selected provider, disables automatic retries for this diagnostic invocation only, and reports a request budget and elapsed time. It never queries telemetry, calls Docker, injects a fault, writes a report or persists a credential. It returns exit 0 on a valid readiness response, otherwise exit 2.

Its request budget uses the same calculation as readiness after disabling diagnostic retries. For a single provider with timeout_seconds = 60 this gives a 65-second budget; there is no hardcoded 45-second probe limit. Existing operator files must be edited explicitly to increase their request timeout.

The output contains category, HTTP status if received, phase, response byte count, finish reason and JSON-validity metadata. It never prints raw response bodies, error messages, request headers, thought signatures or key values.

| Category | Interpretation and next action |
| --- | --- |
| success | The model-only request succeeded in this invocation. Recheck preflight separately; a prior intermittent failure may need timing comparison. |
| http_error | Inspect http_status: 401/403 authentication/access, 404 endpoint/model, 429 quota, 5xx provider availability. Status alone may not establish the precise provider reason. |
| timeout | Compare request timeout, IPv4/IPv6 behavior and network path with curl. connection_or_headers means no response headers were received; response_body means a timeout while reading content. |
| tls_certificate_verification_failed | Check the Python/Ubuntu CA trust store and any required organization certificate. |
| dns_error / network_unreachable / connection_refused | Check name resolution, WSL routing and endpoint reachability. |
| content_not_json | HTTP succeeded but model content violated the JSON contract; finish_reason length suggests truncation. |
| response_schema_invalid / response_json_invalid | The response envelope/body was not valid for the configured backend. |
| response_too_large | The existing Router byte limit was exceeded. |
| unexpected_probe_content | JSON parsed but did not equal the readiness response. |
| configuration_error | No request was made; inspect the existing preflight configuration diagnostics. |

openai_endpoint_matches compares the configured base URL to `https://api.openai.com/v1` when `api_key_env` is `OPENAI_API_KEY`. environment_key_has_outer_whitespace exposes only a boolean. Neither a nonempty key nor an enabled model proves authentication or account access.

This tool improves diagnosis only. It does not claim to fix a live provider failure and does not change F02 metrics timestamp validation. A real failure category is needed before choosing a transport/configuration fix.

The diagnostic makes no changes to the running application, Docker state, telemetry backends or operator files.
