import type { NextApiRequest, NextApiResponse } from 'next';
import CheckoutGateway from '../../gateways/rpc/Checkout.gateway';
import { Empty, OrderResult, PlaceOrderRequest } from '../../protos/demo';

type TResponse = OrderResult | Empty;

const handler = async ({ method, body }: NextApiRequest, res: NextApiResponse<TResponse>) => {
  switch (method) {
    case 'POST': {
      const orderData = body as PlaceOrderRequest;
      const { order } = await CheckoutGateway.placeOrder(orderData);

      return res.status(200).json(order!);
    }

    default: {
      return res.status(405).send('');
    }
  }
};

export default handler;
