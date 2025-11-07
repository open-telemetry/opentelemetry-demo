// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import styled from 'styled-components';

export const ProductReviews = styled.section`
  display: flex;
  margin: 40px 0;
  align-items: center;
  flex-direction: column;
`;

export const TitleContainer = styled.div`
  border-top: 1px dashed;
  padding: 40px 0;
  text-align: center;
  width: 100%;
`;

export const Title = styled.h3`
  font-size: ${({ theme }) => theme.sizes.mLarge};

  ${({ theme }) => theme.breakpoints.desktop} {
    font-size: ${({ theme }) => theme.sizes.dLarge};
  }
`;

/* Summary card at the top */
export const SummaryCard = styled.section`
  width: 100%;
  padding: 20px;
  margin: 0 20px 24px;
  border: 1px solid ${({ theme }) => theme.colors.borderGray};
  border-radius: 8px;
  background: ${({ theme }) => theme.colors.white};
  display: grid;
  gap: 16px;

  ${({ theme }) => theme.breakpoints.desktop} {
    grid-template-columns: 280px 1fr;
    align-items: center;
  }
`;

export const AverageBlock = styled.div`
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: center;
  gap: 12px;
`;

export const AverageScoreBadge = styled.div`
  min-width: 64px;
  height: 64px;
  border-radius: 8px;
  background: ${({ theme }) => theme.colors.otelBlue};
  color: ${({ theme }) => theme.colors.white};
  font-weight: 700;
  font-size: 24px;
  display: grid;
  place-items: center;
`;

export const StarRating = styled.span`
  color: ${({ theme }) => theme.colors.otelYellow};
  font-size: 18px;
`;

export const ScoreCount = styled.span`
  grid-column: 1 / -1;
  color: ${({ theme }) => theme.colors.textLightGray};
  font-size: 14px;
`;

export const ScoreDistribution = styled.div`
  display: grid;
  gap: 8px;
`;

export const ScoreRow = styled.div`
  display: grid;
  grid-template-columns: 80px 1fr 48px;
  align-items: center;
  gap: 8px;
`;

export const ScoreLabel = styled.span`
  font-size: 14px;
  color: ${({ theme }) => theme.colors.textLightGray};
`;

export const ScoreBar = styled.div`
  position: relative;
  height: 10px;
  border-radius: 6px;
  background: ${({ theme }) => theme.colors.lightBorderGray};
  overflow: hidden;
`;

export const ScoreBarFill = styled.div`
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  background: ${({ theme }) => theme.colors.otelBlue};
`;

export const ScorePct = styled.span`
  font-size: 12px;
  color: ${({ theme }) => theme.colors.otelGray};
  text-align: right;
  font-variant-numeric: tabular-nums;
`;

export const SummaryText = styled.p`
  margin: 0;
  line-height: 1.5;
`;

/* Reviews grid: 1 column mobile, 5 desktop (since there are always 5 reviews) */
export const ReviewsGrid = styled.ul`
  display: grid;
  width: 100%;
  padding: 0 20px;
  margin: 0;
  list-style: none;
  gap: 24px;
  grid-template-columns: 1fr;

  ${({ theme }) => theme.breakpoints.desktop} {
    grid-template-columns: repeat(5, 1fr);
  }
`;

export const ReviewCard = styled.li`
  border: 1px solid ${({ theme }) => theme.colors.borderGray};
  border-radius: 8px;
  background: ${({ theme }) => theme.colors.white};
  padding: 16px;
  display: grid;
  gap: 12px;
`;

export const ReviewHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
`;

export const ReviewerName = styled.strong`
  font-weight: 600;
`;

export const ReviewBody = styled.p`
  margin: 0;
  line-height: 1.6;
`;

export const AskAISection = styled.section`
  width: 100%;
  padding: 20px;
  margin: 0 20px 24px;
  border: 1px solid ${({ theme }) => theme.colors.borderGray};
  border-radius: 8px;
  background: ${({ theme }) => theme.colors.white};
  display: grid;
  gap: 12px;
`;

export const AskAIHeader = styled.h4`
  margin: 0;
  font-size: ${({ theme }) => theme.sizes.mLarge};
  color: ${({ theme }) => theme.colors.otelGray};

  ${({ theme }) => theme.breakpoints.desktop} {
    font-size: ${({ theme }) => theme.sizes.dMedium};
  }
`;

export const AskAIInputRow = styled.div`
  display: flex;
  gap: 8px;
  align-items: center;
  width: 100%;
`;

export const AskAIInput = styled.input`
  width: 100%;
  flex: 1;
  min-width: 0;
  padding: 10px 12px;
  border: 1px solid ${({ theme }) => theme.colors.borderGray};
  border-radius: 6px;
  font-size: 16px;
  outline: none;
  background: ${({ theme }) => theme.colors.white};
  color: ${({ theme }) => theme.colors.otelGray};

  &:focus {
    border-color: ${({ theme }) => theme.colors.otelBlue};
    box-shadow: 0 0 0 3px rgba(0, 112, 201, 0.15);
  }
`;

export const AskAIControls = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
`;

export const QuickPromptButton = styled.button`
  padding: 8px 12px;
  border: 1px solid ${({ theme }) => theme.colors.borderGray};
  border-radius: 6px;
  background: ${({ theme }) => theme.colors.white};
  color: ${({ theme }) => theme.colors.otelGray};
  font-size: 14px;
  cursor: pointer;

  &:hover {
    border-color: ${({ theme }) => theme.colors.otelBlue};
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
`;

export const AskAIButton = styled.button`
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  background: ${({ theme }) => theme.colors.otelBlue};
  color: ${({ theme }) => theme.colors.white};
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;

  &:hover {
    filter: brightness(1.05);
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
`;

export const AIMessage = styled.p`
  margin: 0;
  line-height: 1.5;
  color: ${({ theme }) => theme.colors.otelGray};
`;
