// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import * as S from './PlatformFlag.styled';
import useClientValue from '../../utils/hooks/useClientValue';

const PlatformFlag = () => {
  const platform = useClientValue(() => {
    const { NEXT_PUBLIC_PLATFORM = 'local' } = window.ENV;
    return NEXT_PUBLIC_PLATFORM;
  }, 'local');

  return (
    <S.Block>{platform}</S.Block>
  );
};

export default PlatformFlag;
