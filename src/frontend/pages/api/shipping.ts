// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import type { NextApiRequest, NextApiResponse } from 'next';
import InstrumentationMiddleware from '../../utils/telemetry/InstrumentationMiddleware';
import ShippingGateway from '../../gateways/rpc/Shipping.gateway';
import { Address, CartItem, Empty, Money } from '../../protos/demo';
import CurrencyGateway from '../../gateways/rpc/Currency.gateway';
import { context, trace, Exception, SpanStatusCode } from '@opentelemetry/api';

type TResponse = Money | Empty;

const handler = async ({ method, query }: NextApiRequest, res: NextApiResponse<TResponse>) => {
  const tracer = trace.getTracer('frontend');
  const parentSpan = tracer.startSpan('shipping');
  const ctx = trace.setSpan(context.active(), parentSpan);

  switch (method) {
    case 'GET': {
      const { itemList = '', currencyCode = 'USD', address = '' } = query;
      try {
        const spanShipping = tracer.startSpan('shipping', {}, ctx);
        spanShipping.setAttribute('net.peer.name', 'opentelemetry-demo-shippingservice');
        const { costUsd } = await ShippingGateway.getShippingCost(JSON.parse(itemList as string) as CartItem[],
            JSON.parse(address as string) as Address);
        spanShipping.end();

        const spanCurrency = tracer.startSpan('currency', {}, ctx);
        const cost = await CurrencyGateway.convert(costUsd!, currencyCode as string);
        spanCurrency.end();
        return res.status(200).json(cost!);
      } catch (error) {
        parentSpan.recordException(error as Exception);
        parentSpan.setStatus({ code: SpanStatusCode.ERROR });
        return res.status(500).json({ error: 'Internal Server Error' });
      } finally {
        parentSpan.end();
      }
    }

    default: {
      return res.status(405);
    }
  }
};

export default InstrumentationMiddleware(handler);
