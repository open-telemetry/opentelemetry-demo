// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import Link from 'next/link';
import styled from 'styled-components';

export const Container = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 16px;
  padding: 120px 20px;
`;

export const Code = styled.h1`
  font-size: ${({ theme }) => theme.sizes.dxLarge};
  font-weight: ${({ theme }) => theme.fonts.bold};
  color: ${({ theme }) => theme.colors.otelBlue};
  margin: 0;
`;

export const Message = styled.p`
  font-size: ${({ theme }) => theme.sizes.mLarge};
  color: ${({ theme }) => theme.colors.textGray};
  margin: 0;
`;

export const HomeLink = styled(Link)`
  margin-top: 8px;
  background-color: ${({ theme }) => theme.colors.otelBlue};
  color: ${({ theme }) => theme.colors.white};
  display: inline-block;
  padding: 8px 16px;
  font-weight: ${({ theme }) => theme.fonts.semiBold};
  font-size: ${({ theme }) => theme.sizes.mLarge};
  border-radius: 10px;
  text-decoration: none;
`;
