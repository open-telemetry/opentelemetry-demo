// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { ChannelCredentials } from '@grpc/grpc-js';
import {
  GetOrdersByEmailResponse,
  OrderDetail,
  OrderServiceClient,
} from '../../protos/demo';

const { ACCOUNTING_ADDR = '' } = process.env;

const client = new OrderServiceClient(ACCOUNTING_ADDR, ChannelCredentials.createInsecure());

const OrderGateway = () => ({
  getOrdersByEmail(email: string) {
    return new Promise<GetOrdersByEmailResponse>((resolve, reject) =>
      client.getOrdersByEmail({ email }, (error, response) => (error ? reject(error) : resolve(response)))
    );
  },
  getOrder(orderId: string) {
    return new Promise<OrderDetail>((resolve, reject) =>
      client.getOrder({ orderId }, (error, response) => (error ? reject(error) : resolve(response)))
    );
  },
});

export default OrderGateway();
