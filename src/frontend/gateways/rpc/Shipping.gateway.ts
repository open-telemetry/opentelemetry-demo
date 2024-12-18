// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { ChannelCredentials } from '@grpc/grpc-js';
import { Address, CartItem, GetQuoteResponse, ShippingServiceClient } from '../../protos/demo';

const { SHIPPING_ADDR = '' } = process.env;

const client = new ShippingServiceClient(SHIPPING_ADDR, ChannelCredentials.createInsecure());

const ShippingGateway = () => ({
  getShippingCost(itemList: CartItem[], address: Address) {
    return new Promise<GetQuoteResponse>((resolve, reject) =>
      client.getQuote({ items: itemList, address: address }, (error, response) =>
        error ? reject(error) : resolve(response)
      )
    );
  },
});

export default ShippingGateway();
