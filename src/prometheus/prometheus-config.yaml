# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

global:
  scrape_interval: 5s
  scrape_timeout: 3s
  evaluation_interval: 30s

otlp:
  promote_resource_attributes:
    - service.instance.id
    - service.name
    - service.namespace
    - cloud.availability_zone
    - cloud.region
    - container.name
    - deployment.environment.name

scrape_configs:
  - job_name: otel-collector
    static_configs:
      - targets:
          - 'otel-collector:8888'

storage:
  tsdb:
    out_of_order_time_window: 30m
