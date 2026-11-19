// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { useSyncExternalStore } from 'react';

const subscribe = () => () => undefined;

/**
 * Returns `serverValue` during server rendering and hydration, then the value
 * read on the client, so browser-only values do not cause hydration mismatches.
 */
const useClientValue = <T>(getClientValue: () => T, serverValue: T): T =>
  useSyncExternalStore(subscribe, getClientValue, () => serverValue);

export default useClientValue;
