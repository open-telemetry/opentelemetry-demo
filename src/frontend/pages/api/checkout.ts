// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import type { NextApiRequest, NextApiResponse } from 'next';
import type { ServiceError } from '@grpc/grpc-js';
import { context, Exception, SpanStatusCode, trace } from '@opentelemetry/api';
import InstrumentationMiddleware from '../../utils/telemetry/InstrumentationMiddleware';
import CheckoutGateway from '../../gateways/rpc/Checkout.gateway';
import { Empty, PlaceOrderRequest, PlaceOrderResponse } from '../../protos/demo';
import { IProductCheckoutItem, IProductCheckout } from '../../types/Cart';
import ProductCatalogService from '../../services/ProductCatalog.service';

// Prefix checkout's Go service always uses for chargeCard failures (src/checkout/main.go),
// the only signal available to tell a payment decline apart from an unrelated internal error.
const PAYMENT_FAILURE_PREFIX = 'failed to charge card:';

type TResponse = IProductCheckout | Empty | { error: string; code?: string };

const handler = async ({ method, body, query }: NextApiRequest, res: NextApiResponse<TResponse>) => {
  switch (method) {
    case 'POST': {
      const { currencyCode = '' } = query;
      const orderData = body as PlaceOrderRequest;

      let placeOrderResponse: PlaceOrderResponse;
      try {
        placeOrderResponse = await CheckoutGateway.placeOrder(orderData);
      } catch (error) {
        const span = trace.getSpan(context.active());
        span?.recordException(error as Exception);
        span?.setStatus({ code: SpanStatusCode.ERROR });

        const details = (error as ServiceError)?.details || (error as Error)?.message || '';

        if (details.startsWith(PAYMENT_FAILURE_PREFIX)) {
          if (!details.includes('code = Unavailable') && !details.includes('code = Internal')) {
            return res.status(422).json({
              error: 'Your payment could not be processed. Please check your card details and try again.',
              code: 'PAYMENT_FAILED',
            });
          }
        }

        return res.status(500).json({ error: 'Failed to place order.' });
      }

      const { order: { items = [], ...order } = {} } = placeOrderResponse;

      const productList: IProductCheckoutItem[] = await Promise.all(
        items.map(async ({ item: { productId = '', quantity = 0 } = {}, cost }) => {
          const product = await ProductCatalogService.getProduct(productId, currencyCode as string);

          return {
            cost,
            item: {
              productId,
              quantity,
              product,
            },
          };
        })
      );

      return res.status(200).json({ ...order, items: productList });
    }

    default: {
      return res.status(405).send('');
    }
  }
};

export default InstrumentationMiddleware(handler);
