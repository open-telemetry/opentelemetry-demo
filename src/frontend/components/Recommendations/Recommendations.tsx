// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { CypressFields } from '../../utils/enums/CypressFields';
import { useAd } from '../../providers/Ad.provider';
import ProductCard from '../ProductCard';
import * as S from './Recommendations.styled';

const Recommendations = () => {
  const { recommendedProductList } = useAd();

  if (!recommendedProductList || recommendedProductList.length === 0) {
    return null;
  }

  return (
    <S.Recommendations data-cy={CypressFields.RecommendationList}>
      <S.TitleContainer>
        <S.Title>You May Also Like</S.Title>
      </S.TitleContainer>
      <S.ProductList>
        {recommendedProductList.map(product => (
          <ProductCard key={product.id} product={product} />
        ))}
      </S.ProductList>
    </S.Recommendations>
  );
};

export default Recommendations;
