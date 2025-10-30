// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import * as S from './ProductReviews.styled';
import { useProductReview } from '../../providers/ProductReview.provider';
import { useAiAssistant } from '../../providers/ProductAIAssistant.provider';
import React, { useState, useMemo } from 'react';
import { CypressFields } from '../../utils/enums/CypressFields';

const clamp = (n: number, min = 0, max = 5) => Math.max(min, Math.min(max, n));

const StarRating = ({ value, max = 5 }: { value: number; max?: number }) => {
  const rounded = clamp(Math.round(value), 0, max);
  const stars = Array.from({ length: max }, (_, i) => (i < rounded ? '★' : '☆')).join(' ');
  return <S.StarRating aria-label={`${value.toFixed(1)} out of ${max} stars`}>{stars}</S.StarRating>;
};

const ProductReviews = () => {
    const { productReviews, loading, error, averageScore } = useProductReview();

    const average = useMemo(() => {
        if (!averageScore) return null;
        return clamp(Number(averageScore));
    }, [averageScore]);

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

    // AI Assistant (provider-driven)
    const [aiQuestion, setAiQuestion] = useState('');
    const { sendAiRequest, aiResponse, aiLoading, aiError, reset } = useAiAssistant();

    const handleAskAI = (questionOverride?: string) => {
        const q = (questionOverride ?? aiQuestion).trim();
        if (!q) return;
        reset(); // optional: clears previous result
        sendAiRequest({ question: q });
    };

    const handleQuickPrompt = (prompt: string) => {
        setAiQuestion(prompt);
        handleAskAI(prompt);
    };

  return (
    <S.ProductReviews aria-live="polite" data-cy={CypressFields.ProductReviews}>

        <S.AskAISection aria-label="Ask AI about this product" data-cy="AskAISection">
            <S.AskAIHeader>Ask AI About This Product</S.AskAIHeader>

            <S.AskAIInputRow>
                <S.AskAIInput
                    id="ask-ai-input"
                    type="text"
                    placeholder="Type a question about the product…"
                    value={aiQuestion}
                    onChange={(e) => setAiQuestion(e.target.value)}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter' && !aiLoading && aiQuestion.trim()) {
                            handleAskAI();
                        }
                    }}
                    aria-label="Question to AI"
                    data-cy="AskAIInput"
                />
                <S.AskAIButton
                    type="button"
                    onClick={() => handleAskAI()}
                    disabled={aiLoading || !aiQuestion.trim()}
                    aria-busy={aiLoading ? 'true' : 'false'}
                    data-cy="AskAIButton"
                >
                    {aiLoading ? 'Asking AI…' : 'Ask'}
                </S.AskAIButton>
            </S.AskAIInputRow>

            <S.AskAIControls>
                <S.QuickPromptButton
                    type="button"
                    onClick={() => handleQuickPrompt('Can you summarize the product reviews?')}
                    data-cy="QuickPromptSummarize"
                >
                    Can you summarize the product reviews?
                </S.QuickPromptButton>

                <S.QuickPromptButton
                    type="button"
                    onClick={() => handleQuickPrompt('What age(s) is this recommended for?')}
                    data-cy="QuickPromptAges"
                >
                    What age(s) is this recommended for?
                </S.QuickPromptButton>

                <S.QuickPromptButton
                    type="button"
                    onClick={() => handleQuickPrompt('Were there any negative reviews?')}
                    data-cy="QuickPromptNegative"
                >
                    Were there any negative reviews?
                </S.QuickPromptButton>
            </S.AskAIControls>

            {aiError && (
                <S.AIMessage role="alert" data-cy="AIError">
                    {aiError.message ?? 'Sorry, something went wrong while asking AI.'}
                </S.AIMessage>
            )}

            {aiResponse && (
                <S.AIMessage aria-live="polite" data-cy="AIAnswer">
                    <strong>AI Response:</strong>{' '}
                    {typeof aiResponse === 'string' ? aiResponse : aiResponse.text}
                </S.AIMessage>
            )}
        </S.AskAISection>


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
                {(average != null) && (
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
