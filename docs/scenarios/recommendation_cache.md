# Using Metrics and Traces to diagnose a memory leak.

Application telemetry, such as the kind that OpenTelemetry can provide, is very
useful for diagnosing issues in a distributed system. In this scenario, we will
walk through a scenario demonstrating how to move from high-level metrics and
traces to determine the cause of a memory leak.

## Setup

To run this scenario, you will need to deploy the demo application and enable
the `recommendationCache` feature flag.

## Determining that a problem exists

The first step in diagnosing a problem is to determine that a problem exists.
Often the first stop will be a metrics dashboard provided by a tool such as
Grafana.

The 