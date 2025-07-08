// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import * as S from './PlatformFlag.styled';

const { NEXT_PUBLIC_PLATFORM = 'local' } = typeof window !== 'undefined' ? window.ENV : {};

const platform = NEXT_PUBLIC_PLATFORM;

const PlatformFlag = () => {
  // Using suppressHydrationWarning here because the current setup renders differently on the server (server is always "local" and client whatever was configured as "ENV_PLATFORM")
  return <S.Block suppressHydrationWarning>{platform}</S.Block>;
};

export default PlatformFlag;
