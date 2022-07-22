import styled from 'styled-components';

export const Cart = styled.div`
  width: 60%;
  margin: 56px auto;
`;

export const Container = styled.div`
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 86px;
  margin-bottom: 112px;

  @media (max-width: 766px) {
    grid-template-columns: 1fr;
  }
`;

export const Header = styled.div`
  display: flex;
  justify-content: space-between;
  margin-bottom: 24px;
  align-items: center;
`;

export const CarTitle = styled.h1`
  margin: 0;
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

export const EmptyCartContainer = styled.div`
  display: grid;
  grid-template-columns: 487px;
  gap: 28px;
  align-items: flex-end;
  justify-content: center;
  margin-bottom: 120px;
`;
