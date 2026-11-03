// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useState } from 'react';
import * as S from './Clock.styled';

const Clock = () => {
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    setNow(new Date());
    const interval = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);

  if (!now) return null;

  return (
    <S.Clock dateTime={now.toISOString()} title={now.toLocaleDateString()}>
      {now.toLocaleTimeString()}
    </S.Clock>
  );
};

export default Clock;
