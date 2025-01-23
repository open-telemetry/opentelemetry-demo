// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { ChannelCredentials } from '@grpc/grpc-js';
import { AdResponse, AdServiceClient } from '../../protos/demo';

const { AD_ADDR = '' } = process.env;

const client = new AdServiceClient(AD_ADDR, ChannelCredentials.createInsecure());

const AdGateway = () => ({
  listAds(contextKeys: string[]) {
    return new Promise<AdResponse>((resolve, reject) =>
      client.getAds({ contextKeys: contextKeys }, (error, response) => (error ? reject(error) : resolve(response)))
    );
  },
});

export default AdGateway();
