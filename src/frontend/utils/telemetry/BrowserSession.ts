// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import {
  createDefaultSessionIdGenerator,
  createLocalStorageSessionStore,
  createSessionManager,
} from '@opentelemetry/browser-sdk/session';

export const sessionManager = createSessionManager({
  sessionIdGenerator: createDefaultSessionIdGenerator(),
  sessionStore: createLocalStorageSessionStore(),
  maxDuration: 4 * 60 * 60,
  inactivityTimeout: 30 * 60,
});
