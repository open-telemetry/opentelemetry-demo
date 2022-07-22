import styled from 'styled-components';
import Button from '../components/Button';

export const ProductDetail = styled.div`
  width: 70%;
  margin: 56px auto;
`;

export const Container = styled.div`
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 28px;
  align-items: flex-end;
  margin-bottom: 112px;

  @media (max-width: 766px) {
    grid-template-columns: 1fr;
  }
`;

export const Image = styled.img`
  width: 100%;
  height: auto;
  border-radius: 20% 20% 0 20%;
`;

export const Details = styled.div`
  display: flex;
  flex-direction: column;
  gap: 16px;
`;

export const AddToCart = styled(Button)`
  width: 110px;
`;
