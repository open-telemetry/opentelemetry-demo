import styled from 'styled-components';

export const CartItems = styled.section`
  display: flex;
  flex-direction: column;
`;

export const CartItemImage = styled.img`
  width: 100%;
  height: auto;
  border-radius: 20% 0 20% 20%;
`;

export const CartItem = styled.div`
  display: grid;
  grid-template-columns: 40% 1fr;
  gap: 24px;
  padding: 24px 0;
  border-top: solid 1px rgba(154, 160, 166, 0.5);
`;

export const CartItemDetails = styled.div`
  display: flex;
  flex-direction: column;
  justify-content: space-between;
`;

export const PriceContainer = styled.div`
  display: flex;
  width: 100%;
  justify-content: space-between;
`;

export const DataRow = styled.div`
  display: flex;
  justify-content: space-between;
  padding: 24px 0;
  border-top: solid 1px rgba(154, 160, 166, 0.5);
`;

export const TotalText = styled.h3`
  margin: 0;
`;
