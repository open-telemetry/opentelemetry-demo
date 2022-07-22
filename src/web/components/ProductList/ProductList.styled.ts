import styled from 'styled-components';

export const ProductList = styled.div`
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 32px;

  @media (max-width: 766px) {
    grid-template-columns: 1fr;
  }
`;
