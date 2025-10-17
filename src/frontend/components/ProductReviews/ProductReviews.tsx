// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import * as S from './ProductReviews.styled';
import { useProductReview } from '../../providers/ProductReview.provider';
import { useEffect, useMemo } from 'react';

const clamp = (n: number, min = 0, max = 5) => Math.max(min, Math.min(max, n));

const StarRating = ({ value, max = 5 }: { value: number; max?: number }) => {
  const rounded = clamp(Math.round(value), 0, max);
  const stars = Array.from({ length: max }, (_, i) => (i < rounded ? '★' : '☆')).join(' ');
  return <S.StarRating aria-label={`${value.toFixed(1)} out of ${max} stars`}>{stars}</S.StarRating>;
};

const ProductReviews = () => {
    const { productReviews, loading, error, productReviewSummary } = useProductReview();

    useEffect(() => {
    console.log('productReviews changed:', productReviews);
    }, [productReviews]);

    const summaryText =
    productReviewSummary?.productReviewSummary ??
    '';

    const average = useMemo(() => {
    if (!productReviewSummary?.averageScore) return null;
    return clamp(Number(productReviewSummary.averageScore));
    }, [productReviewSummary]);

    const distribution = useMemo(() => {
        if (!Array.isArray(productReviews)) return [0, 0, 0, 0, 0];
        const counts = [0, 0, 0, 0, 0];
        for (const r of productReviews) {
            const s = clamp(Math.round(Number(r.score)), 1, 5); // round first, clamp to [1,5]
            counts[s - 1] += 1;
        }
        return counts;
    }, [productReviews]);

    const normalizedPercents = useMemo(() => {
        if (!Array.isArray(productReviews) || productReviews.length === 0) return [0, 0, 0, 0, 0];

        const raw = distribution.map(c => (c / productReviews.length) * 100);
        const floored = raw.map(p => Math.floor(p));
        const sumFloors = floored.reduce((a, b) => a + b, 0);
        let remainder = 100 - sumFloors;

        const order = raw
            .map((p, i) => ({ i, frac: p - Math.floor(p) }))
            .sort((a, b) => b.frac - a.frac);

        const final = floored.slice();
        for (let k = 0; k < remainder; k++) {
            final[order[k].i] += 1;
        }
        return final;
    }, [distribution, productReviews]);

  return (
    <S.ProductReviews aria-live="polite">
      <S.TitleContainer>
        <S.Title>Customer Reviews</S.Title>
      </S.TitleContainer>

        {loading && <p>Loading product reviews…</p>}

        {!loading && error && <p>Could not load product reviews.</p>}

        {!loading && !error && Array.isArray(productReviews) && productReviews.length === 0 && (
        <p>No reviews yet.</p>
        )}

        {!loading && !error && (
            <>
                {(average != null || summaryText) && (
                    <S.SummaryCard>
                        {average != null && (
                            <>
                                <S.AverageBlock>
                                    <S.AverageScoreBadge>{average.toFixed(1)}</S.AverageScoreBadge>
                                    <StarRating value={average} />
                                    <S.ScoreCount>
                                        {Array.isArray(productReviews) ? `${productReviews.length} reviews` : ''}
                                    </S.ScoreCount>
                                </S.AverageBlock>

                                {Array.isArray(productReviews) && productReviews.length > 0 && (
                                    <S.ScoreDistribution>
                                        {[1, 2, 3, 4, 5].map((score, idx) => {
                                            const pct = normalizedPercents[idx];
                                            return (
                                                <S.ScoreRow key={`score-${score}`}>
                                                    <S.ScoreLabel>
                                                        {score} star{score > 1 ? 's' : ''}
                                                    </S.ScoreLabel>
                                                    <S.ScoreBar aria-label={`${score} stars: ${pct}%`}>
                                                        <S.ScoreBarFill style={{ width: `${pct}%` }} />
                                                    </S.ScoreBar>
                                                    <S.ScorePct>{pct}%</S.ScorePct>
                                                </S.ScoreRow>
                                            );
                                        })}
                                    </S.ScoreDistribution>
                                )}
                            </>
                        )}

                        {summaryText && (
                            <S.SummaryText>
                                <strong>AI Summary:</strong> {summaryText}
                            </S.SummaryText>
                        )}
                    </S.SummaryCard>
                )}

          {Array.isArray(productReviews) && productReviews.length > 0 && (
            <S.ReviewsGrid as="ul">
              {productReviews.map((review, idx) => (
                <S.ReviewCard as="li" key={`${review.username}-${review.score}-${idx}`}>
                  <S.ReviewHeader>
                    <S.ReviewerName>{review.username}</S.ReviewerName>
                    <StarRating value={Number(review.score) || 0} />
                  </S.ReviewHeader>
                  <S.ReviewBody>
                    {review.description || 'No description provided.'}
                  </S.ReviewBody>
                </S.ReviewCard>
              ))}
            </S.ReviewsGrid>
          )}
        </>
      )}
    </S.ProductReviews>
  );
};

export default ProductReviews;