// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import {ChannelCredentials} from '@grpc/grpc-js';
import {
    ListFlagsResponse,
    FeatureFlagServiceClient,
    PlaceOrderRequest,
    PlaceOrderResponse,
    UpdateFlagRequest, UpdateFlagResponse
} from '../../protos/demo';

const {FEATURE_FLAG_GRPC_SERVICE_ADDR = ''} = process.env;

const client = new FeatureFlagServiceClient(FEATURE_FLAG_GRPC_SERVICE_ADDR, ChannelCredentials.createInsecure());

const FeatureFlagGateway = () => ({
    listFeatureFlags() {
        return new Promise<ListFlagsResponse>((resolve, reject) =>
            client.listFlags({}, (error, response) => (error ? reject(error) : resolve(response)))
        );
    },

    updateFeatureFlag(name: string, enabled: number) {
        return new Promise<UpdateFlagResponse>((resolve, reject) => client.updateFlag({
                name: name,
                enabled
            }, (error, response) => (error ? reject(error) : resolve(response)))
        );
    },
});

export default FeatureFlagGateway();
