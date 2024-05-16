// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import Link from 'next/link';
import styled from 'styled-components';

export const Header = styled.header`
  background-color: #853b5c;
  color: white;
`;

export const NavBar = styled.nav`
  height: 80px;
  background-color: white;
  font-size: 15px;
  color: #b4b2bb;
  border-bottom: 1px solid ${({ theme }) => theme.colors.textGray};
  z-index: 1;
  padding: 0;

  ${({ theme }) => theme.breakpoints.desktop} {
    height: 100px;
  }
`;

export const Container = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  height: 100%;
  padding: 0 20px;

  ${({ theme }) => theme.breakpoints.desktop} {
    padding: 25px 100px;
  }
`;

export const NavBarBrand = styled(Link)`
  display: flex;
  align-items: center;
  padding: 0;
`;

export const BrandImg = styled.img.attrs({
  src: '/images/opentelemetry-demo-logo.png',
})`
  width: 280px;
  height: auto;
`;

export const Controls = styled.div`
  display: flex;
  height: 60px;
`;
