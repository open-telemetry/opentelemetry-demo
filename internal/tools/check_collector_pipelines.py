#!/usr/bin/env python3
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# The collector replaces (not appends) arrays when merging --config layers, so a
# layer that sets a pipeline's receivers, processors or exporters must repeat every
# entry already set by the layers loaded before it.

import sys

import yaml

CONFIG_DIR = 'src/otel-collector'
# Load order used by compose.observability.yaml. otelcol-config-extras.yml is left
# out because forks may replace lists there on purpose.
LAYERS = [
    f'{CONFIG_DIR}/otelcol-config.yml',
    f'{CONFIG_DIR}/otelcol-config-full.yml',
    f'{CONFIG_DIR}/otelcol-config-observability.yml',
]
KEYS = ('receivers', 'processors', 'exporters')


def pipelines(path):
    with open(path) as f:
        config = yaml.safe_load(f) or {}
    return (config.get('service') or {}).get('pipelines') or {}


merged = {}
errors = 0
for layer in LAYERS:
    for name, pipeline in pipelines(layer).items():
        current = merged.setdefault(name, {})
        for key in KEYS:
            if key not in (pipeline or {}):
                continue
            missing = [c for c in current.get(key, []) if c not in pipeline[key]]
            if missing:
                errors += 1
                print(
                    f'{layer}: pipelines.{name}.{key} drops {missing} set by earlier config layers',
                    file=sys.stderr,
                )
            current[key] = pipeline[key]

sys.exit(1 if errors else 0)
