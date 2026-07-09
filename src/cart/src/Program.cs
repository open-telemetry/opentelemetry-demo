// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
using System;
using System.Net.Security;
using System.Net.WebSockets;

using Grpc.Health.V1;
using Microsoft.AspNetCore.Diagnostics.HealthChecks;
using System.Threading.Tasks;
using System.Threading;

using Grpc.Core;

using cart.cartstore;
using cart.services;
using cart.healthcheck;

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
using OpenFeature.Providers.Flagd;
using OpenTelemetry.OpAmp.Client;
using OpenTelemetry.OpAmp.Client.Settings;

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

// Report this service's status to the demo's OpAMP server when running with the
// observability stack. This showcases OpAMP as a control plane for an
// SDK-instrumented application, alongside the Collector.
OpAmpClient opAmpClient = null;
var opampEndpoint = builder.Configuration["OPAMP_SERVER_ENDPOINT"];
if (!string.IsNullOrEmpty(opampEndpoint))
{
    var opAmpLogger = app.Services.GetRequiredService<ILogger<Program>>();
    try
    {
        opAmpClient = new OpAmpClient(opts =>
        {
            opts.ConnectionType = ConnectionType.WebSocket;
            opts.ServerUrl = new Uri(opampEndpoint);
            opts.Identification.AddIdentifyingAttribute("service.name", builder.Environment.ApplicationName);
            opts.Identification.AddNonIdentifyingAttribute("telemetry.sdk.language", "dotnet");

            // The demo's OpAMP server uses a self-signed certificate, so skip
            // certificate validation for the demo's wss:// connection.
            opts.ClientWebSocketFactory = () =>
            {
                var socket = new ClientWebSocket();
                socket.Options.RemoteCertificateValidationCallback =
                    (sender, certificate, chain, sslPolicyErrors) => true;
                return socket;
            };
        });

        await opAmpClient.StartAsync();
    }
    catch (Exception ex)
    {
        opAmpLogger.LogWarning(ex, "Failed to start OpAMP client");
        opAmpClient = null;
    }
}

var ValkeyCartStore = (ValkeyCartStore)app.Services.GetRequiredService<ICartStore>();
app.Services.GetRequiredService<StackExchangeRedisInstrumentation>().AddConnection(ValkeyCartStore.GetConnection());

app.MapGrpcService<CartService>();
app.MapGrpcService<HealthServiceImpl>();

app.MapGet("/", async context =>
{
    await context.Response.WriteAsync("Communication with gRPC endpoints must be made through a gRPC client. To learn how to create a client, visit: https://go.microsoft.com/fwlink/?linkid=2086909");
});

app.Run();

if (opAmpClient != null)
{
    await opAmpClient.StopAsync();
    opAmpClient.Dispose();
}


