// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import {ChannelCredentials, status} from '@grpc/grpc-js';
import {
    CreateFlagRequest,
    CreateFlagResponse,
    DeleteFlagResponse,
    FeatureFlagServiceClient,
    GetFlagResponse,
    ListFlagsResponse,
    UpdateFlagProbabilityRequest,
    UpdateFlagProbabilityResponse
} from '../../protos/demo';

const {FEATURE_FLAG_GRPC_SERVICE_ADDR = ''} = process.env;

const client = new FeatureFlagServiceClient(FEATURE_FLAG_GRPC_SERVICE_ADDR, ChannelCredentials.createInsecure());

const FeatureFlagGateway = () => ({

    getFeatureFlag(name: string) {
        return new Promise<GetFlagResponse>((resolve, reject) =>
            client.getFlag({name}, (error, response) => (error ? reject(error) : resolve(response)))
        );
    },

    createFeatureFlag(flag: CreateFlagRequest) {
        return new Promise<CreateFlagResponse>((resolve, reject) =>
            client.createFlag(flag, (error, response) => (error ? reject(error) : resolve(response)))
        );
    },

    updateFeatureFlag(name: string, flag: UpdateFlagProbabilityRequest) {
        return new Promise<UpdateFlagProbabilityResponse>((resolve, reject) => client.updateFlagProbability(flag, (error, response) => (error ? reject(error) : resolve(response)))
        );
    },

    listFeatureFlags() {
        return new Promise<ListFlagsResponse>((resolve, reject) =>
            client.listFlags({}, (error, response) => (error ? reject(error) : resolve(response)))
        );
    },

    deleteFeatureFlag(name: string) {
        return new Promise<DeleteFlagResponse>((resolve, reject) => client.deleteFlag({name},
                (error, response) => {
                    if (error) {
                        if (error.code === status.NOT_FOUND) {
                            return resolve({} as DeleteFlagResponse)
                        } else {
                            return reject(error)
                        }
                    }
                    resolve(response)
                }
            )
        );
    },

});

export default FeatureFlagGateway();
