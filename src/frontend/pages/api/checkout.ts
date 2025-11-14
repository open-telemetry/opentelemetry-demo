// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import type { NextApiRequest, NextApiResponse } from 'next';
import InstrumentationMiddleware from '../../utils/telemetry/InstrumentationMiddleware';
import CheckoutGateway from '../../gateways/rpc/Checkout.gateway';
import { Empty, PlaceOrderRequest } from '../../protos/demo';
import { IProductCheckoutItem, IProductCheckout } from '../../types/Cart';
import ProductCatalogService from '../../services/ProductCatalog.service';
import { trace } from '@opentelemetry/api';

type TResponse = IProductCheckout | Empty;

const handler = async ({ method, body, query }: NextApiRequest, res: NextApiResponse<TResponse>) => {
  switch (method) {
    case 'POST': {
      const { currencyCode = '' } = query;
      const orderData = body as PlaceOrderRequest;
      const { order: { items = [], ...order } = {} } = await CheckoutGateway.placeOrder(orderData);

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

      // Create a custom backend span for order confirmation
      const orderId = 'orderId' in order ? order.orderId : '';
      const tracer = trace.getTracer('frontend-api');
      const span = tracer.startSpan('order.confirmed', {
        attributes: {
          'order.id': orderId,
          'order.items_count': productList.length,
          'order.total_items': productList.reduce((sum, item) => sum + item.item.quantity, 0),
          'order.currency': currencyCode as string,
          'order.user_id': orderData.userId || '',
        },
      });

      console.log('Backend order confirmation span created:', {
        orderId,
        itemsCount: productList.length,
        totalItems: productList.reduce((sum, item) => sum + item.item.quantity, 0),
      });

      // End the span immediately as this is a marker span
      span.end();

      return res.status(200).json({ ...order, items: productList });
    }

    default: {
      return res.status(405).send('');
    }
  }
};

export default InstrumentationMiddleware(handler);
