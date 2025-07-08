// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

const prefix = 'persisted_call';

export function persistedCall<T>(key: string, fn: () => T): () => T {
  return () => {
    const persistedResult = sessionStorage.getItem(`${prefix}_${key}`);

    if (persistedResult) {
      try {
        return JSON.parse(persistedResult) as T;
      } catch (err) {
        // ignoring
      }
    }

    const result = fn();
    sessionStorage.setItem(`${prefix}_${key}`, JSON.stringify(result));
    return result;
  };
}
