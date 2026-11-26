// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import styled from 'styled-components';
import Button from '../Button';

export const Toggle = styled(Button)`
  position: fixed;
  right: 20px;
  bottom: 20px;
  min-height: 44px;
  height: auto;
  font-size: ${({ theme }) => theme.sizes.dSmall};
  z-index: 1000;

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.otelBlue};
    outline-offset: 2px;
  }
`;

export const Panel = styled.section`
  position: fixed;
  right: 0;
  bottom: 80px;
  width: 100%;
  height: min(70dvh, 520px);
  max-height: calc(100dvh - 100px);
  display: flex;
  flex-direction: column;
  background: ${({ theme }) => theme.colors.white};
  z-index: 1001;

  button:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.otelBlue};
    outline-offset: 2px;
  }

  button:disabled {
    opacity: 0.6;
    cursor: default;
  }
  border-radius: 10px;
  box-shadow: 0 2px 2px 0 rgb(0 0 0 / 14%), 0 3px 1px -2px rgb(0 0 0 / 12%), 0 1px 5px 0 rgb(0 0 0 / 20%);

  ${({ theme }) => theme.breakpoints.desktop} {
    right: 20px;
    bottom: 80px;
    width: 400px;
    height: 520px;
    border-radius: 10px;
  }
`;

export const Header = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid ${({ theme }) => theme.colors.lightBorderGray};
`;

export const Title = styled.h2`
  margin: 0;
  font-size: ${({ theme }) => theme.sizes.dMedium};
`;

export const Close = styled(Button)`
  min-height: 44px;
  height: auto;
  padding: 0 8px;
  font-size: ${({ theme }) => theme.sizes.dMedium};
`;

export const MessageList = styled.div`
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

export const Message = styled.p<{ $role: 'user' | 'assistant' }>`
  margin: 0;
  padding: 8px 12px;
  border-radius: 10px;
  max-width: 85%;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: ${({ theme }) => theme.sizes.dSmall};
  align-self: ${({ $role }) => ($role === 'user' ? 'flex-end' : 'flex-start')};
  color: ${({ $role, theme }) => ($role === 'user' ? theme.colors.white : theme.colors.textGray)};
  background: ${({ $role, theme }) => ($role === 'user' ? theme.colors.otelBlue : theme.colors.backgroundGray)};
`;

export const Status = styled.p`
  margin: 0;
  font-size: ${({ theme }) => theme.sizes.dSmall};
  color: ${({ theme }) => theme.colors.textGray};
`;

export const Form = styled.form`
  display: flex;
  flex-wrap: wrap;
  flex-shrink: 0;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid ${({ theme }) => theme.colors.lightBorderGray};
`;

export const Label = styled.label`
  width: 100%;
  font-size: ${({ theme }) => theme.sizes.dSmall};
`;

export const Input = styled.input`
  flex: 1;
  min-width: 0;
  padding: 8px 12px;

  font-size: ${({ theme }) => theme.sizes.dSmall};
  border-radius: 10px;
  background: ${({ theme }) => theme.colors.white};
  border: 1px solid ${({ theme }) => theme.colors.lightBorderGray};

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.otelBlue};
    outline-offset: 2px;
  }
`;

export const Send = styled(Button)`
  min-height: 44px;
  height: auto;
  font-size: ${({ theme }) => theme.sizes.dSmall};
`;
