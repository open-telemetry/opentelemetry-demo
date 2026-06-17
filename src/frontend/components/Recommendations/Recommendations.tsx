// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';
import { CypressFields } from '../../utils/enums/CypressFields';
import { useAd } from '../../providers/Ad.provider';
import ProductCard from '../ProductCard';
import * as S from './Recommendations.styled';
import { maybeCaptureProductRecommendationError } from '../../utils/controlledIssues';

const Recommendations = () => {
  const { recommendedProductList } = useAd();
  const { pathname, query } = useRouter();
  const [hideRecommendations, setHideRecommendations] = useState(false);

  useEffect(() => {
    const productId = typeof query.productId === 'string' ? query.productId : undefined;
    const shouldHide = maybeCaptureProductRecommendationError({
      page: pathname,
      productId,
    });

    if (shouldHide) setHideRecommendations(true);
  }, [pathname, query.productId]);

  if (hideRecommendations || !recommendedProductList || recommendedProductList.length === 0) {
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
