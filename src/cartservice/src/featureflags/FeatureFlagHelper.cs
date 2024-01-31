// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
using System;
using System.Threading.Tasks;
using Oteldemo;

namespace cartservice.featureflags;

public class FeatureFlagHelper
{
    private static readonly Random Random = new();
    private readonly FeatureFlagService.FeatureFlagServiceClient _featureFlagServiceClient;

    public FeatureFlagHelper()
    {
        var featureFlagServiceAddress = Environment.GetEnvironmentVariable("FEATURE_FLAG_GRPC_SERVICE_ADDR");
        if (string.IsNullOrEmpty(featureFlagServiceAddress))
        {
            _featureFlagServiceClient = null;
        } else {
            var featureFlagServiceUri = new Uri($"http://{Environment.GetEnvironmentVariable("FEATURE_FLAG_GRPC_SERVICE_ADDR")}");
            var channel = Grpc.Net.Client.GrpcChannel.ForAddress(featureFlagServiceUri);
            _featureFlagServiceClient = new FeatureFlagService.FeatureFlagServiceClient(channel);
        }
    }

    public async Task<bool> GenerateCartError()
    {
        if (_featureFlagServiceClient == null)
        {
            return false;
        }

        var featureFlagRequest = new EvaluateProbabilityFeatureFlagRequest { Name = "cartServiceFailure" };
        var featureFlagResponse = await _featureFlagServiceClient.EvaluateProbabilityFeatureFlagAsync(featureFlagRequest);
        return featureFlagResponse.Enabled;
    }
}
