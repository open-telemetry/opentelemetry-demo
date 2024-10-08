// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import type { NextApiRequest, NextApiResponse } from 'next';
import InstrumentationMiddleware from '../../../utils/telemetry/InstrumentationMiddleware';
import { Empty, Product } from '../../../protos/demo';
import ProductCatalogService from '../../../services/ProductCatalog.service';
import { context, trace, Exception } from '@opentelemetry/api';

type TResponse = Product[] | Empty;

const handler = async ({ method, query }: NextApiRequest, res: NextApiResponse<TResponse>) => {
  const tracer = trace.getTracer('frontend');
  const parentSpan = tracer.startSpan('cart');
  const ctx = trace.setSpan(context.active(), parentSpan);

  switch (method) {
    case 'GET': {
      const { currencyCode = '' } = query;
      
      try {
        // net.peer.name
        const spanProduct = tracer.startSpan('product', {}, ctx);
        spanProduct.setAttribute('net.peer.name', 'opentelemetry-demo-productcatalogservice');
        const productList = await ProductCatalogService.listProducts(currencyCode as string);
        spanProduct.end();
        return res.status(200).json(productList);
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
