// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

const { start } = require('@splunk/otel');

start({
    serviceName: process.env.OTEL_SERVICE_NAME || 'payment',
});
