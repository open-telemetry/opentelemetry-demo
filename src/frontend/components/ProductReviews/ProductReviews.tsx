// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import * as S from './ProductReviews.styled';
import { useProductReview } from '../../providers/ProductReview.provider';
import { useEffect } from 'react';

const ProductReviews = () => {
    const { productReviews, loading, error } = useProductReview();
    console.log('productReviews:', productReviews);
    console.log('typeof(productReviews):', typeof(productReviews));
    console.log('Array.isArray(productReviews):', Array.isArray(productReviews));

    if (productReviews != null) {
        console.log('productReviews.length:', productReviews.length);
    }

    useEffect(() => {
        console.log('productReviews changed:', productReviews);
    }, [productReviews]);

    return (
        <S.ProductReviews>
            <S.TitleContainer>
                <S.Title>Product Reviews</S.Title>
            </S.TitleContainer>

            {loading && <p>Loading product reviews…</p>}

            {!loading && error && (
                <p>Could not load product reviews.</p>
            )}

            {!loading && !error && productReviews != null && (
                <S.ProductReviewList>
                    {productReviews.map((review) => (
                        <li key={review.username}>
                            <p><strong>{review.username}</strong></p>
                            <p>{review.description}</p>
                            <p>Score: {review.score}</p>
                        </li>
                    ))}
                </S.ProductReviewList>
            )}
        </S.ProductReviews>
    );
};

export default ProductReviews;
