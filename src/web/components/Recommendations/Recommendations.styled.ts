import styled from 'styled-components';

export const Recommendations = styled.section`
  display: flex;
  width: 80%;
  align-items: center;
  flex-direction: column;
  margin: 0 auto;
`;

export const ProductList = styled.div`
  display: grid;
  grid-template-columns: 1fr 1fr 1fr 1fr;
  gap: 24px;

  @media (max-width: 766px) {
    grid-template-columns: 1fr;
  }
`;

export const TitleContainer = styled.div`
  border-top: solid 1px;
  padding: 40px 0;
  font-weight: normal;
  text-align: center;
  width: 100%;
`;
