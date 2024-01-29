// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import type { NextApiRequest, NextApiResponse } from 'next';
import FeatureFlagGateway from '../../../gateways/rpc/FeatureFlag.gateway';
import { FlagProbability, Empty } from '../../../protos/demo';

type TResponse = FlagProbability[] | Empty;

const handler = async ({ method }: NextApiRequest, res: NextApiResponse<TResponse>) => {
  switch (method) {
    case 'GET': {
      const { flag } = await FeatureFlagGateway.listFeatureFlags();
      return res.status(200).json(flag);
    }

    default: {
      return res.status(405).send('');
    }
  }
};

export default handler;
