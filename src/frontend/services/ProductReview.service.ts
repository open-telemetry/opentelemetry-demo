// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import ProductReviewGateway from '../gateways/rpc/ProductReview.gateway';

const ProductReviewService = () => ({

    async getProductReviews(id: string) {
        const productReviews = await ProductReviewGateway.getProductReviews(id);

        return productReviews;
    },
    async getAverageProductReviewScore(id: string) {
        const averageScore = await ProductReviewGateway.getAverageProductReviewScore(id);

        return averageScore;
    },
    async askProductAIAssistant(id: string, question: string) {
        const response = await ProductReviewGateway.askProductAIAssistant(id, question);

        return response;
    },
});

export default ProductReviewService();
