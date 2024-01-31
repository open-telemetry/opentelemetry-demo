// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import type {NextApiRequest, NextApiResponse} from 'next';
import FeatureFlagGateway from '../../../../gateways/rpc/FeatureFlag.gateway';
import {
    Empty,
    EvaluateProbabilityFeatureFlagResponse,
    GetFeatureFlagValueResponse,
    UpdateFlagValueRequest,
} from '../../../../protos/demo';

type TResponse = Empty | GetFeatureFlagValueResponse | EvaluateProbabilityFeatureFlagResponse;

const handler = async ({method, query, body}: NextApiRequest, res: NextApiResponse<TResponse>) => {
    switch (method) {
        case 'GET': {
            const {name = '', mode = 'raw'} = query
            switch (mode as string) {
                case 'probability':
                    const randomDecisionOutcome = await FeatureFlagGateway.evaluateProbabilityFeatureFlag(name as string);
                    return res.status(200).json(randomDecisionOutcome);
                case 'range':
                    const range = await FeatureFlagGateway.getRangeFeatureFlag(name as string);
                    return res.status(200).json(range);
                case 'raw':
                // fall through
                default:
                    const flag = await FeatureFlagGateway.getFeatureFlagValue(name as string);
                    return res.status(200).json(flag);
            }
        }

        case 'PUT': {
            const {name} = query
            if (!name || Array.isArray(name)) {
                return res.status(400).end()
            }
            if (!body || typeof body.value !== 'number') {
                return res.status(400).end()
            }
            const updateFlagProbabilityRequest = body as UpdateFlagValueRequest;
            // The name is part of the resource path, and we do not want to require clients to repeat the name in the request
            // body; but on the grpc level the name needs to be in the message body, so we move it there.
            updateFlagProbabilityRequest.name = name;
            await FeatureFlagGateway.updateFlagValue(name as string, updateFlagProbabilityRequest);
            return res.status(204).end();
        }

        case 'DELETE': {
            const {name = ''} = query
            await FeatureFlagGateway.deleteFlag(name as string);
            return res.status(204).end();
        }

        default: {
            return res.status(405).end();
        }
    }
};

export default handler;
