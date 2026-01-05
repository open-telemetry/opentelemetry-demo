// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
using System;

using Grpc.HealthCheck;
using Grpc.Health.V1;
using Microsoft.AspNetCore.Diagnostics.HealthChecks;
using System.Threading.Tasks;
using System.Threading;

using Grpc.Core;

using cart.cartstore;
using cart.services;

using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Diagnostics.HealthChecks;
using Microsoft.Extensions.Logging;
using OpenTelemetry.Instrumentation.StackExchangeRedis;
using OpenTelemetry.Logs;
using OpenTelemetry.Metrics;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;
using OpenFeature;
using OpenFeature.Hooks;
using OpenFeature.Contrib.Providers.Flagd;

var builder = WebApplication.CreateBuilder(args);
string valkeyAddress = builder.Configuration["VALKEY_ADDR"];
if (string.IsNullOrEmpty(valkeyAddress))
{
    Console.WriteLine("VALKEY_ADDR environment variable is required.");
    Environment.Exit(1);
}

builder.Logging
    .AddOpenTelemetry(options => options.AddOtlpExporter())
    .AddConsole();

builder.Services.AddSingleton<ICartStore>(x =>
{
    var store = new ValkeyCartStore(x.GetRequiredService<ILogger<ValkeyCartStore>>(), valkeyAddress);
    store.Initialize();
    return store;
});

builder.Services.AddOpenFeature(openFeatureBuilder =>
{
    openFeatureBuilder
        .AddProvider(_ => new FlagdProvider())
        .AddHook<MetricsHook>()
        .AddHook<TraceEnricherHook>();
});

builder.Services.AddSingleton(x =>
    new CartService(
        x.GetRequiredService<ICartStore>(),
        new ValkeyCartStore(x.GetRequiredService<ILogger<ValkeyCartStore>>(), "badhost:1234"),
        x.GetRequiredService<IFeatureClient>()
));


Action<ResourceBuilder> appResourceBuilder =
    resource => resource
        .AddService(builder.Environment.ApplicationName)
        .AddContainerDetector()
        .AddHostDetector();

builder.Services.AddOpenTelemetry()
    .ConfigureResource(appResourceBuilder)
    .WithTracing(tracerBuilder => tracerBuilder
        .AddSource("OpenTelemetry.Demo.Cart")
        .AddRedisInstrumentation(
            options => options.SetVerboseDatabaseStatements = true)
        .AddAspNetCoreInstrumentation()
        .AddGrpcClientInstrumentation()
        .AddHttpClientInstrumentation()
        .AddOtlpExporter())
    .WithMetrics(meterBuilder => meterBuilder
        .AddMeter("OpenTelemetry.Demo.Cart")
        .AddMeter("OpenFeature")
        .AddProcessInstrumentation()
        .AddRuntimeInstrumentation()
        .AddAspNetCoreInstrumentation()
        .SetExemplarFilter(ExemplarFilterType.TraceBased)
        .AddOtlpExporter());
builder.Services.AddGrpc();
builder.Services.AddSingleton<readinessCheck>();
builder.Services.AddGrpcHealthChecks()
    .AddCheck<readinessCheck>("oteldemo.CartService");

builder.Services.AddSingleton<HealthServiceImpl>(); 

var app = builder.Build();

var ValkeyCartStore = (ValkeyCartStore)app.Services.GetRequiredService<ICartStore>();
app.Services.GetRequiredService<StackExchangeRedisInstrumentation>().AddConnection(ValkeyCartStore.GetConnection());

app.MapGrpcService<CartService>();
app.MapGrpcService<HealthServiceImpl>();

app.MapGet("/", async context =>
{
    await context.Response.WriteAsync("Communication with gRPC endpoints must be made through a gRPC client. To learn how to create a client, visit: https://go.microsoft.com/fwlink/?linkid=2086909");
});

app.Run();
public class readinessCheck : IHealthCheck
{
        private readonly IFeatureClient _featureClient;

    public readinessCheck(IFeatureClient featureClient)
    {
        _featureClient = featureClient;
    }
    public async Task<HealthCheckResult> CheckHealthAsync(HealthCheckContext context, CancellationToken cancellationToken = default)
    {
    
    // Await the async call instead of blocking
        bool isSet = await _featureClient.GetBooleanValueAsync("failedReadinessProbe", false); // Replace with actual check

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
            _logger.LogInformation("Received health check request for service: {Service}", request.Service);
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
            var serviceHealth = await _healthCheckService.CheckHealthAsync(registration => MatchesService(registration, request.Service),cancellationToken);
            return new HealthCheckResponse
            {
                Status = ConvertToGrpcStatus(serviceHealth.Entries[request.Service].Status)
            };
        }

        private bool MatchesService(HealthCheckRegistration registration, string service)
        {
            return registration.Name == service;
        }
        public override async Task Watch(HealthCheckRequest request, IServerStreamWriter<HealthCheckResponse> responseStream, ServerCallContext context)
        {
            _logger.LogInformation("Received health watch request for service: {Service}", request.Service);

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

