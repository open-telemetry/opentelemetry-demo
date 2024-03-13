// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import type { Config } from 'jest';

const config: Config = {
  testEnvironment: 'node',
  clearMocks: true,
  coverageProvider: 'v8',
  modulePathIgnorePatterns: ['.next'],
};

export default config;
