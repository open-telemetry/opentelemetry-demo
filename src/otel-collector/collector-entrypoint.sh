#!/bin/sh
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

if [ "${1:-}" = "featuregate" ]; then
  exec /otelcol-contrib "$@"
fi

exec /otelcol-contrib "$@" --feature-gates=service.profilesSupport
