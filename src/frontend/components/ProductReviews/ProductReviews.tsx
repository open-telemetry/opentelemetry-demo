// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import * as S from './ProductReviews.styled';
import { useProductReview } from '../../providers/ProductReview.provider';
import { useEffect } from 'react';

const ProductReviews = () => {
    const { productReviews, loading, error, productReviewSummary } = useProductReview();

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

            {!loading && !error && Array.isArray(productReviews) && productReviews.length === 0 && (
                <p>No reviews yet.</p>
            )}

            {productReviewSummary != null && (
                <p>Average Score: {productReviewSummary.averageScore}</p>
            )}

            {productReviewSummary != null && (
                <p>Summary: {productReviewSummary.productReviewSummary}</p>
            )}

            {!loading && !error && Array.isArray(productReviews) && productReviews.length > 0 && (
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
