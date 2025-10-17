// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import type { NextApiRequest, NextApiResponse } from 'next';
import InstrumentationMiddleware from '../../../../utils/telemetry/InstrumentationMiddleware';
import { Empty, GetProductReviewSummaryResponse } from '../../../../protos/demo';
import ProductReviewService from '../../../../services/ProductReview.service';

type TResponse = GetProductReviewSummaryResponse | Empty;

const handler = async ({ method, query }: NextApiRequest, res: NextApiResponse<TResponse>) => {

    switch (method) {
        case 'GET': {
            const { productId = '' } = query;

            const productReviewSummary = await ProductReviewService.getProductReviewSummary(productId as string);

            return res.status(200).json(productReviewSummary);
        }

        default: {
            return res.status(405).send('');
        }
    }
};

export default InstrumentationMiddleware(handler);
