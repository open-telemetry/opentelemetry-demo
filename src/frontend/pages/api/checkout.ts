// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import type { NextApiRequest, NextApiResponse } from 'next';
import InstrumentationMiddleware from '../../utils/telemetry/InstrumentationMiddleware';
import CheckoutGateway from '../../gateways/rpc/Checkout.gateway';
import { Empty, PlaceOrderRequest } from '../../protos/demo';
import { IProductCheckoutItem, IProductCheckout } from '../../types/Cart';
import ProductCatalogService from '../../services/ProductCatalog.service';

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

      return res.status(200).json({ ...order, items: productList });
    }

    default: {
      return res.status(405).send('');
    }
  }
};

export default InstrumentationMiddleware(handler);
