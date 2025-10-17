// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import ProductReviewGateway from '../gateways/rpc/ProductReview.gateway';
import {ProductReview} from '../protos/demo';

const ProductReviewService = () => ({

    async getProductReviews(id: string) {
        const productReviews = await ProductReviewGateway.getProductReviews(id);

        return {
            ...productReviews
        };
    },
});

export default ProductReviewService();
