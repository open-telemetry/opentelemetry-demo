# Recommendation Service Health-Check Runbook

## Summary

The OpenTelemetry Demo minimal environment failed to complete startup because
Docker reported the recommendation service as unhealthy.

The application was running, but its container health check could not execute.

## Symptoms

Docker Compose reported:

    dependency failed to start: container recommendation is unhealthy

The frontend, load-generator, and frontend-proxy containers remained in the
Created state.

The recommendation health check reported:

    /bin/sh: 1: nc: not found

## Impact

Docker marked the recommendation service as unhealthy. Services configured to
wait for it were prevented from starting, making the application frontend
unavailable.

## Root Cause

The original health check used the `nc` utility to test the recommendation
service port. The downloaded recommendation image did not contain `nc`, so the
health check returned exit code 127 even though the application port was
reachable.

## Resolution

A portfolio-specific Compose override replaces the unavailable `nc` command
with a Bash TCP connection test.

The Makefile includes `compose.portfolio.yaml` after the core Compose file so
the override is applied automatically.

## Validation

The following checks passed:

- Docker Compose configuration validation
- Recommendation port 9001 connectivity test
- Recommendation health check with exit code 0
- Fresh minimal-environment deployment
- All required application containers started
- Storefront returned HTTP status 200
- Grafana database status reported as ok
- Jaeger displayed application traces
- Load generator produced synthetic traffic

## Rollback

To remove the override:

1. Remove `-f compose.portfolio.yaml` from `DOCKER_COMPOSE_FILES_CORE` in the Makefile.
2. Remove `compose.portfolio.yaml`.
3. Validate the original Compose configuration.
4. Recreate the minimal environment.

## Known Minimal-Mode Warning

The shared OpenTelemetry Collector configuration attempts to scrape Kafka
metrics even though Kafka is excluded from minimal mode. This produces
`kafka:9092` name-resolution warnings but does not stop other application
telemetry from being collected.

Kafka receiver handling will be addressed separately so this change remains
focused on the recommendation health-check failure.