// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import type { NextApiHandler } from 'next';
import CartGateway from '../../gateways/rpc/Cart.gateway';
import { AddItemRequest, Empty } from '../../protos/demo';
import ProductCatalogService from '../../services/ProductCatalog.service';
import { IProductCart, IProductCartItem } from '../../types/Cart';
import InstrumentationMiddleware from '../../utils/telemetry/InstrumentationMiddleware';
import { context, Exception, SpanStatusCode, trace } from '@opentelemetry/api';

type TResponse = IProductCart | Empty;

const handler: NextApiHandler<TResponse> = async ({ method, body, query }, res) => {
  const tracer = trace.getTracer('frontend');
  const parentSpan = tracer.startSpan('cart');
  const ctx = trace.setSpan(context.active(), parentSpan);
  
  switch (method) {
    case 'GET': {
      const { sessionId = '', currencyCode = '' } = query;
      try {
        // net.peer.name 
        const spanCart = tracer.startSpan('cart', {}, ctx);
        spanCart.setAttribute('net.peer.name', 'opentelemetry-demo-cartservice');
        const { userId, items } = await CartGateway.getCart(sessionId as string);
        spanCart.end();

        
        const productList: IProductCartItem[] = await Promise.all(
          items.map(async ({ productId, quantity }) => {
            const spanProduct = tracer.startSpan('product', {}, ctx);
            spanProduct.setAttribute('net.peer.name', 'opentelemetry-demo-productcatalogservice');
            const product = await ProductCatalogService.getProduct(productId, currencyCode as string);
            spanProduct.end();

            return {
              productId,
              quantity,
              product,
            };
          })
        );

        return res.status(200).json({ userId, items: productList });
      } catch (error) {
        parentSpan.recordException(error as Exception);
        parentSpan.setStatus({ code: SpanStatusCode.ERROR });
        return res.status(500).json({ error: 'Internal Server Error' });
      } finally {
        parentSpan.end();
      }
    }

    case 'POST': {
      const { userId, item } = body as AddItemRequest;

      try {
        // net.peer.name
        const spanCart = tracer.startSpan('cart', {}, ctx);
        spanCart.setAttribute('net.peer.name', 'opentelemetry-demo-cartservice');
        await CartGateway.addItem(userId, item!);
        const cart = await CartGateway.getCart(userId);
        spanCart.end();

        return res.status(200).json(cart);
      } catch (error) {
        parentSpan.recordException(error as Exception);
        parentSpan.setStatus({ code: SpanStatusCode.ERROR });
        return res.status(500).json({ error: 'Internal Server Error' });
      } finally {
        parentSpan.end();
      }
    }

    case 'DELETE': {
      const { userId } = body as AddItemRequest;

      try {
        // net.peer.name
        const spanCart = tracer.startSpan('cart', {}, ctx);
        spanCart.setAttribute('net.peer.name', 'opentelemetry-demo-cartservice');
        await CartGateway.emptyCart(userId);
        spanCart.end();

        return res.status(204).send('');
      } catch (error) {
        parentSpan.recordException(error as Exception);
        parentSpan.setStatus({ code: SpanStatusCode.ERROR });
        return res.status(500).send('');
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
