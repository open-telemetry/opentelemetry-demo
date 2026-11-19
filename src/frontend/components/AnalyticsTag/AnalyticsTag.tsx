// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { useEffect } from 'react';
import { useNumberFlagValue } from '@openfeature/react-sdk';

const trackClick = (events: number) => {
  const queue = Array.from({ length: events }, (_, i) => ({
    id: i,
    type: 'click',
    path: `/product/${i % 10}`,
    ts: i,
    value: Math.sin(i) * 100,
  }));
  const batch: typeof queue = JSON.parse(JSON.stringify(queue));
  batch.sort((a, b) => a.path.localeCompare(b.path) || a.ts - b.ts);
  const body = JSON.stringify(batch);
  let hash = 0;
  for (let i = 0; i < body.length; i++) {
    hash = (hash * 31 + body.charCodeAt(i)) | 0;
  }
  return hash;
};

/**
 * Stands in for a third-party analytics tag that serializes, sorts and
 * fingerprints its event queue synchronously on every click. The queue size
 * comes from the webInteractionSlowdown feature flag, and 0 turns the tag off.
 */
const AnalyticsTag = () => {
  const events = useNumberFlagValue('webInteractionSlowdown', 0);

  useEffect(() => {
    if (events <= 0) return;

    const onClick = () => trackClick(events);

    document.addEventListener('click', onClick);
    return () => document.removeEventListener('click', onClick);
  }, [events]);

  return null;
};

export default AnalyticsTag;
