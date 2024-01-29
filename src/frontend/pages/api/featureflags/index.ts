// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import type {NextApiRequest, NextApiResponse} from 'next';
import FeatureFlagGateway from '../../../gateways/rpc/FeatureFlag.gateway';
import {CreateFlagRequest, Empty, FlagDefinition} from '../../../protos/demo';

type TResponse = FlagDefinition[] | FlagDefinition | Empty;

const handler = async ({method, body}: NextApiRequest, res: NextApiResponse<TResponse>) => {
    switch (method) {
        case 'POST': {
            if (!body || typeof body.name !== 'string' || typeof body.description !== 'string' || typeof body.enabled !== 'number') {
                return res.status(400).end()
            }
            const flagFromRequest = body as CreateFlagRequest
            const {flag: flagFromResponse} = await FeatureFlagGateway.createFeatureFlag(flagFromRequest);
            return res.status(200).json(flagFromResponse!);
        }

        case 'GET': {
            const {flag: allFlags} = await FeatureFlagGateway.listFeatureFlags();
            return res.status(200).json(allFlags);
        }

        default: {
            return res.status(405).send('');
        }
    }
};

export default handler;
