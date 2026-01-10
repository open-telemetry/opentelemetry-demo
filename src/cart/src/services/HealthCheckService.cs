// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using System;

using Grpc.Core;
using Grpc.HealthCheck;
using Grpc.Health.V1;
using System.Threading.Tasks;
using System.Threading;

using OpenFeature;
using OpenFeature.Hooks;
using OpenFeature.Contrib.Providers.Flagd;

using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Diagnostics.HealthChecks;
using Microsoft.Extensions.Logging;

namespace cart.healthcheck
{
    public class readinessCheck : IHealthCheck
    {
        private readonly IFeatureClient _featureClient;

        public readinessCheck(IFeatureClient featureClient)
        {
            _featureClient = featureClient;
        }
        public async Task<HealthCheckResult> CheckHealthAsync(HealthCheckContext context, CancellationToken cancellationToken = default)
        {

            #pragma warning disable CA2016 // OpenFeature does not support CancellationToken
            // Await the async call instead of blocking
            bool isSet = await _featureClient.GetBooleanValueAsync("failedReadinessProbe", false); // Replace with actual check
            #pragma warning restore CA2016
            if (isSet)
            {
                return HealthCheckResult.Unhealthy("connection failed");

            }

            return HealthCheckResult.Healthy("healthy");
        }
    }


    public class HealthServiceImpl : Health.HealthBase
    {
        private readonly ILogger<HealthServiceImpl> _logger;
        private readonly HealthCheckService _healthCheckService;


        public HealthServiceImpl(
            ILogger<HealthServiceImpl> logger,
            HealthCheckService healthCheckService)
        {
            _logger = logger;
            _healthCheckService = healthCheckService;
        }

        public override async Task<HealthCheckResponse> Check(HealthCheckRequest request, ServerCallContext context)
        {
           if (_logger.IsEnabled(LogLevel.Information))
           {
            _logger.LogInformation("Received health check request for service: {Service}", request.Service);
           }
            var cancellationToken = context.CancellationToken;
            // If service is empty or null, check overall health
            if (string.IsNullOrEmpty(request.Service))
            {
                var health = await _healthCheckService.CheckHealthAsync(cancellationToken);
                return new HealthCheckResponse
                {
                    Status = ConvertToGrpcStatus(health.Status)
                };
            }

            // You can implement service-specific health checks here
            // This example checks a specific service
            var serviceHealth = await _healthCheckService.CheckHealthAsync(registration => MatchesService(registration, request.Service), cancellationToken);
            return new HealthCheckResponse
            {
                Status = ConvertToGrpcStatus(serviceHealth.Entries[request.Service].Status)
            };
        }

        private static bool MatchesService(HealthCheckRegistration registration, string service)
        {
            return registration.Name == service;
        }

        public override async Task Watch(HealthCheckRequest request, IServerStreamWriter<HealthCheckResponse> responseStream, ServerCallContext context)
        {
            if (_logger.IsEnabled(LogLevel.Information))
            {
            _logger.LogInformation("Received health watch request for service: {Service}", request.Service);
            }
            // Simple implementation to send current status once
            var response = await Check(request, context);
            await responseStream.WriteAsync(response);

            // In a real implementation, you would periodically check health and send updates
            // This might involve setting up a timer or listener for health changes
        }

        private static HealthCheckResponse.Types.ServingStatus ConvertToGrpcStatus(HealthStatus status)
        {
            return status switch
            {
                HealthStatus.Healthy => HealthCheckResponse.Types.ServingStatus.Serving,
                HealthStatus.Degraded => HealthCheckResponse.Types.ServingStatus.Serving, // Or you might want to use SERVING_WITH_ISSUES if available
                HealthStatus.Unhealthy => HealthCheckResponse.Types.ServingStatus.NotServing,
                _ => HealthCheckResponse.Types.ServingStatus.Unknown
            };
        }
    }
}
