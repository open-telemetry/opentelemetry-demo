# Frontend Proxy Service

This service acts as a reverse proxy for the various user-facing web interfaces.

## Modifying the Envoy Configuration

The envoy configuration is generated from the `envoy.tmpl.yaml` file in this
directory. Environment variables are substituted at deploy-time.

The `/api/assistant` route lets the frontend enforce its two-minute agent
deadline. Other frontend requests keep the default proxy timeout.

## Test the assistant route

On Linux with Docker, Python 3 and PyYAML installed (also installed by yamllint),
run this from the repository root:

```shell
python3 src/frontend-proxy/test_assistant.py
```

The test renders the full configuration and runs the Envoy image pinned in the
Dockerfile. A local HTTP stand-in for the frontend takes 16 seconds to reply.
Assistant requests, including a query string, must succeed, while other frontend
paths still time out. The test removes its container and temporary files on exit.
