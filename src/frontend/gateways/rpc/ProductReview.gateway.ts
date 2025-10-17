// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { ChannelCredentials } from '@grpc/grpc-js';
import {ProductReview, ProductReviewServiceClient, GetProductReviewSummaryResponse} from '../../protos/demo';

const { PRODUCT_REVIEWS_ADDR = '' } = process.env;

const client = new ProductReviewServiceClient(PRODUCT_REVIEWS_ADDR, ChannelCredentials.createInsecure());

const ProductReviewGateway = () => ({

    getProductReviews(productId: string) {
        return new Promise<ProductReview []>((resolve, reject) =>
            client.getProductReviews({ productId }, (error, response) => (error ? reject(error) : resolve(response.productReviews)))
        );
    },
    getProductReviewSummary(productId: string) {
        return new Promise<GetProductReviewSummaryResponse>((resolve, reject) =>
            client.getProductReviewSummary({ productId }, (error, response) => (error ? reject(error) : resolve(response)))
        );
    },
});

export default ProductReviewGateway();
