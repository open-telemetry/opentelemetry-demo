import Link from 'next/link';
import styled from 'styled-components';

export const CartIcon = styled(Link).attrs({
  as: 'a',
})`
  position: relative;
  display: block;
  margin-left: 25px;
  display: flex;
  flex-flow: column;
  align-items: center;
  justify-content: center;
`;

export const Icon = styled.img`
  width: 20px;
  height: 20px;
  margin-bottom: 3px;
`;

export const ItemsCount = styled.span`
  display: flex;
  align-items: center;
  justify-content: center;
  position: absolute;
  top: 24px;
  left: 11px;
  width: 16px;
  height: 16px;
  font-size: 11px;
  border-radius: 4px 4px 0 4px;
  color: white;
  background-color: #853b5c;
`;
