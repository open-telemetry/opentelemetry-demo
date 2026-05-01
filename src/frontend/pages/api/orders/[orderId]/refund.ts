// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import type { NextApiRequest, NextApiResponse } from 'next';
import InstrumentationMiddleware from '../../../../utils/telemetry/InstrumentationMiddleware';
import OrderGateway from '../../../../gateways/rpc/Order.gateway';
import PaymentGateway from '../../../../gateways/rpc/Payment.gateway';

const handler = async ({ method, query, body }: NextApiRequest, res: NextApiResponse) => {
  switch (method) {
    case 'POST': {
      const { orderId } = query;
      const { email } = body;
      if (typeof email !== 'string' || !email) {
        return res.status(400).json({ error: 'email required' });
      }

      const order = await OrderGateway.getOrder(orderId as string);

      if ((order.email || '').toLowerCase() !== email.toLowerCase()) {
        return res.status(403).json({ error: 'email does not match order' });
      }
      if (order.status !== 'completed') {
        return res.status(409).json({ error: `order cannot be refunded (status: ${order.status})` });
      }

      // Payment owns the refund; on success it publishes a RefundResult to the
      // "refunds" topic. The accounting consumer marks the order refunded
      // asynchronously, so this response returns before order.status flips.
      const refund = await PaymentGateway.refund({
        orderId: order.orderId,
        transactionId: order.transactionId,
        amount: order.totalCost,
        email,
      });

      return res.status(200).json(refund);
    }

    default: {
      return res.status(405).send('');
    }
  }
};

export default InstrumentationMiddleware(handler);
