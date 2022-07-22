import styled from 'styled-components';

export const Checkout = styled.div`
  width: 70%;
  margin: 56px auto;
`;

export const Container = styled.div`
  display: grid;
  grid-template-columns: 487px;
  gap: 28px;
  align-items: flex-end;
  justify-content: center;
  margin-bottom: 120px;
`;

export const DataRow = styled.div`
  display: grid;
  justify-content: space-between;
  grid-template-columns: 1fr 1fr;
  padding: 24px 0;
  border-top: solid 1px rgba(154, 160, 166, 0.5);

  span:last-of-type {
    text-align: right;
  }
`;

export const Title = styled.h1`
  text-align: center;
  margin: 0;
`;

export const Subtitle = styled.h3`
  text-align: center;
  margin: 0;
`;

export const ButtonContainer = styled.div`
  display: flex;
  justify-content: center;
  align-items: center;
`;
