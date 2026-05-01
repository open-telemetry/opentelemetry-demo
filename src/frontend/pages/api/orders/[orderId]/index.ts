// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import type { NextApiRequest, NextApiResponse } from 'next';
import InstrumentationMiddleware from '../../../../utils/telemetry/InstrumentationMiddleware';
import OrderGateway from '../../../../gateways/rpc/Order.gateway';

const handler = async ({ method, query }: NextApiRequest, res: NextApiResponse) => {
  switch (method) {
    case 'GET': {
      const { orderId } = query;
      const order = await OrderGateway.getOrder(orderId as string);

      return res.status(200).json(order);
    }

    default: {
      return res.status(405).send('');
    }
  }
};

export default InstrumentationMiddleware(handler);
