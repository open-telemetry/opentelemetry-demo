// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import ProductReviewGateway from '../gateways/rpc/ProductReview.gateway';

const ProductReviewService = () => ({

    async getProductReviews(id: string) {
        const productReviews = await ProductReviewGateway.getProductReviews(id);

        return productReviews;
    },
    async getProductReviewSummary(id: string) {
        const productReviewSummary = await ProductReviewGateway.getProductReviewSummary(id);

        return productReviewSummary;
    },
});

export default ProductReviewService();
