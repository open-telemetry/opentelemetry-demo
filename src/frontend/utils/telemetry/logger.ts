// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import pino from 'pino';

const logger = pino({
  level: process.env.LOG_LEVEL || 'info',
});

export default logger;
