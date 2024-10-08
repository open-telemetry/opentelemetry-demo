// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import type { NextApiRequest, NextApiResponse } from 'next';
import InstrumentationMiddleware from '../../utils/telemetry/InstrumentationMiddleware';
import CheckoutGateway from '../../gateways/rpc/Checkout.gateway';
import { Empty, PlaceOrderRequest } from '../../protos/demo';
import { IProductCheckoutItem, IProductCheckout } from '../../types/Cart';
import ProductCatalogService from '../../services/ProductCatalog.service';
import { context, Exception, trace } from '@opentelemetry/api';

type TResponse = IProductCheckout | Empty;

const handler = async ({ method, body, query }: NextApiRequest, res: NextApiResponse<TResponse>) => {
  const tracer = trace.getTracer('frontend');
  const parentSpan = tracer.startSpan('checkout');
  const ctx = trace.setSpan(context.active(), parentSpan);
  
  switch (method) {
    case 'POST': {
      const { currencyCode = '' } = query;

      try {
        const orderData = body as PlaceOrderRequest;

        // net.peer.name 
        const spanCheckout = tracer.startSpan('checkoutservice', {}, ctx);
        spanCheckout.setAttribute('net.peer.name', 'opentelemetry-demo-checkoutservice');
        const { order: { items = [], ...order } = {} } = await CheckoutGateway.placeOrder(orderData);
        spanCheckout.end();

        // net.peer.name 
        const spanProduct = tracer.startSpan('productcatalogservice', {}, ctx);
        spanProduct.setAttribute('net.peer.name', 'opentelemetry-demo-productcatalogservice');
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
        spanProduct.end();
        return res.status(200).json({ ...order, items: productList });
    } catch (error) {
      parentSpan.recordException(error as Exception);
      return res.status(500).json({ error: 'Internal Server Error' });
    } finally {
      parentSpan.end();
    }
  }

    default: {
      return res.status(405).send('');
    }
  }
};

export default InstrumentationMiddleware(handler);
