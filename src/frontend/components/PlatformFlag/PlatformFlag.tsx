// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useState } from 'react';
import * as S from './PlatformFlag.styled';

const PlatformFlag = () => {
  const [platform, setPlatform] = useState('local');

  useEffect(() => {
    const { NEXT_PUBLIC_PLATFORM = 'local' } = window.ENV;
    setPlatform(NEXT_PUBLIC_PLATFORM);
  }, []);

  return (
    <S.Block>{platform}</S.Block>
  );
};

export default PlatformFlag;
