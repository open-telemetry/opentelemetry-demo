// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import styled from 'styled-components';

export const Block = styled.div`
  position: absolute;
  bottom: 0;
  right: 0;
  width: 100px;
  height: 27px;
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: ${({ theme }) => theme.sizes.mSmall};
  font-weight: ${({ theme }) => theme.fonts.regular};
  color: ${({ theme }) => theme.colors.white};
  background: ${({ theme }) => theme.colors.otelYellow};

  ${({ theme }) => theme.breakpoints.desktop} {
    width: 190px;
    height: 50px;
    font-size: ${({ theme }) => theme.sizes.dSmall};
  }
`;
