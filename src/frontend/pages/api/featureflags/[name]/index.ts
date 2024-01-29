// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import type { NextApiRequest, NextApiResponse } from 'next';
import FeatureFlagGateway from '../../../../gateways/rpc/FeatureFlag.gateway';
import { UpdateFlagResponse, UpdateFlagRequest} from '../../../../protos/demo';

const handler = async ({ method, query, body }: NextApiRequest, res: NextApiResponse<UpdateFlagResponse>) => {
  switch (method) {
    case 'PUT': {
      const {name=''} = query
      await FeatureFlagGateway.updateFeatureFlag(name as string, (body as UpdateFlagRequest).enabled);
      return res.status(204).send('');
    }

    default: {
      return res.status(405).send('');
    }
  }
};

export default handler;
