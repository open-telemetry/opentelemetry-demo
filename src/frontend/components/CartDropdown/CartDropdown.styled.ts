// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import Image from 'next/image';
import styled from 'styled-components';
import Button from '../Button';

export const CartDropdown = styled.div`
  position: fixed;
  top: 0;
  right: 0;
  width: 100%;
  height: 100%;
  max-height: 100%;
  padding: 5px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24px;
  background: ${({ theme }) => theme.colors.white};
  z-index: 1000;
  border-radius: 5px;
  box-shadow: 0 2px 2px 0 rgb(0 0 0 / 14%), 0 3px 1px -2px rgb(0 0 0 / 12%), 0 1px 5px 0 rgb(0 0 0 / 20%);

  ${({ theme }) => theme.breakpoints.desktop} {
    position: absolute;
    width: 400px;
    top: 95px;
    right: 17px;
    max-height: 600px;
  }
`;

export const Title = styled.h5`
  margin: 0px;
  font-size: ${({ theme }) => theme.sizes.mxLarge};

  ${({ theme }) => theme.breakpoints.desktop} {
    font-size: ${({ theme }) => theme.sizes.dLarge};
  }
`;

export const ItemList = styled.div`
  ${({ theme }) => theme.breakpoints.desktop} {
    max-height: 450px;
    overflow-y: auto;
  }
`;

export const Item = styled.div`
  display: grid;
  grid-template-columns: 29% 59%;
  gap: 2%;
  padding: 25px 0;
  border-bottom: 1px solid ${({ theme }) => theme.colors.textLightGray};
`;

export const ItemImage = styled(Image).attrs({
  width: '80',
  height: '80',
})`
  border-radius: 5px;
  object-fit: contain;
`;

export const ItemName = styled.p`
  margin: 0px;
  font-size: ${({ theme }) => theme.sizes.mLarge};
  font-weight: ${({ theme }) => theme.fonts.regular};
`;

export const ItemDetails = styled.div`
  display: flex;
  flex-direction: column;
  gap: 5px;
`;

export const ItemQuantity = styled(ItemName)`
  font-size: ${({ theme }) => theme.sizes.mMedium};
`;

export const CartButton = styled(Button)``;

export const ContentWrapper = styled.div`
  width: 100%;
  overflow-y: auto;
  flex: 1;
  min-height: 0;

  ${({ theme }) => theme.breakpoints.desktop} {
    overflow-y: visible;
    flex: 0 1 auto;
    min-height: auto;
  }
`;

export const Header = styled.div`
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;

  span {
    position: absolute;
    right: 25px;
  }

  ${({ theme }) => theme.breakpoints.desktop} {
    span {
      display: none;
    }
  }
`;

export const EmptyCart = styled.h3`
  margin: 0;
  margin-top: 25px;
  font-size: ${({ theme }) => theme.sizes.mLarge};
  color: ${({ theme }) => theme.colors.textLightGray};
  text-align: center;
`;
