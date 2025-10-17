// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { ChannelCredentials } from '@grpc/grpc-js';
import {GetProductReviewsResponse, ProductReviewServiceClient} from '../../protos/demo';

const { PRODUCT_REVIEWS_ADDR = '' } = process.env;

const client = new ProductReviewServiceClient(PRODUCT_REVIEWS_ADDR, ChannelCredentials.createInsecure());

const ProductReviewGateway = () => ({

    getProductReviews(productId: string) {
        return new Promise<GetProductReviewsResponse>((resolve, reject) =>
            client.getProductReviews({ productId }, (error, response) => (error ? reject(error) : resolve(response)))
        );
    },
});

export default ProductReviewGateway();
