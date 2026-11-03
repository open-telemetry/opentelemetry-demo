// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import styled from 'styled-components';

export const Clock = styled.time`
  display: none;
  align-items: center;
  font-size: ${({ theme }) => theme.sizes.dSmall};
  font-weight: ${({ theme }) => theme.fonts.regular};
  font-variant-numeric: tabular-nums;
  color: #605f64;

  ${({ theme }) => theme.breakpoints.desktop} {
    display: flex;
  }
`;
