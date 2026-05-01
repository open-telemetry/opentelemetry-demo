// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { ChannelCredentials } from '@grpc/grpc-js';
import {
  PaymentServiceClient,
  RefundRequest,
  RefundResponse,
} from '../../protos/demo';

const { PAYMENT_ADDR = '' } = process.env;

const client = new PaymentServiceClient(PAYMENT_ADDR, ChannelCredentials.createInsecure());

const PaymentGateway = () => ({
  refund(request: RefundRequest) {
    return new Promise<RefundResponse>((resolve, reject) =>
      client.refund(request, (error, response) => (error ? reject(error) : resolve(response)))
    );
  },
});

export default PaymentGateway();
