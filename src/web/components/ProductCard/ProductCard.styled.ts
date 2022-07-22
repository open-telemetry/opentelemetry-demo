import styled from 'styled-components';
import RouterLink from 'next/link';

export const Link = styled(RouterLink).attrs({
  as: 'a',
})`
  position: relative;
  display: block;
`;

export const Image = styled.img`
  width: 100%;
  height: auto;
  border-radius: 20% 0 20% 20%;
`;

export const Overlay = styled.img`
  position: absolute;
  height: 100%;
  width: 100%;
  top: 0;
  left: 0;
  border-radius: 20% 0 20% 20%;
  background-color: transparent;
`;

export const ProductCard = styled.div`
  &:hover ${Overlay} {
    background-color: rgba(71, 0, 29, 0.2);
  }
`;

export const ProductName = styled.h5`
  margin: 0;
  margin-top: 18px;
`;
