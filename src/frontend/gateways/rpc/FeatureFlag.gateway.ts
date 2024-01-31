// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import {ChannelCredentials, status} from '@grpc/grpc-js';
import {
    CreateFlagRequest,
    CreateFlagResponse,
    DeleteFlagResponse, EvaluateProbabilityFeatureFlagResponse,
    FeatureFlagServiceClient, GetFeatureFlagValueResponse,
    ListFlagsResponse, UpdateFlagValueRequest, UpdateFlagValueResponse,
} from '../../protos/demo';

const {FEATURE_FLAG_GRPC_SERVICE_ADDR = ''} = process.env;

const client = new FeatureFlagServiceClient(FEATURE_FLAG_GRPC_SERVICE_ADDR, ChannelCredentials.createInsecure());

const FeatureFlagGateway = () => ({

    getFeatureFlagValue(name: string) {
        return new Promise<GetFeatureFlagValueResponse>((resolve, reject) =>
            client.getFeatureFlagValue({name}, (error, response) => (error ? reject(error) : resolve(response)))
        );
    },

    evaluateProbabilityFeatureFlag(name: string) {
        return new Promise<EvaluateProbabilityFeatureFlagResponse>((resolve, reject) =>
            client.evaluateProbabilityFeatureFlag({name}, (error, response) => (error ? reject(error) : resolve(response)))
        );
    },

    createFlag(flag: CreateFlagRequest) {
        return new Promise<CreateFlagResponse>((resolve, reject) =>
            client.createFlag(flag, (error, response) => (error ? reject(error) : resolve(response)))
        );
    },

    updateFlagValue(name: string, flag: UpdateFlagValueRequest) {
        return new Promise<UpdateFlagValueResponse>((resolve, reject) => client.updateFlagValue(flag, (error, response) => (error ? reject(error) : resolve(response)))
        );
    },

    listFlags() {
        return new Promise<ListFlagsResponse>((resolve, reject) =>
            client.listFlags({}, (error, response) => (error ? reject(error) : resolve(response)))
        );
    },

    deleteFlag(name: string) {
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
