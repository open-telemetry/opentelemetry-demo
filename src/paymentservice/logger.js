// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

const bunyan = require('bunyan');
module.exports = bunyan.createLogger({ name: 'paymentservice' });
