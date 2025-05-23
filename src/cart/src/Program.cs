// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
using System;

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
using OpenFeature.Contrib.Providers.Flagd;
using OpenFeature.Contrib.Hooks.Otel;

var builder = WebApplication.CreateBuilder(args);


builder.Logging
    .AddOpenTelemetry(options => options.AddOtlpExporter())
    .AddConsole();

builder.Services.AddSingleton<ICartStore>(x =>
{
    var store = new DaprStateManagementCartStore(x.GetRequiredService<ILogger<DaprStateManagementCartStore>>(), "cart-state-store");

    store.Initialize();
    return store;
});

builder.Services.AddOpenFeature(openFeatureBuilder =>
{
    openFeatureBuilder
        .AddHostedFeatureLifecycle()
        .AddProvider(_ => new FlagdProvider());
});

builder.Services.AddSingleton(x =>
    new CartService(
        x.GetRequiredService<ICartStore>(),
        new DaprStateManagementCartStore(x.GetRequiredService<ILogger<DaprStateManagementCartStore>>(), "bad-state-store"),
        x.GetRequiredService<IFeatureClient>()
));


Action<ResourceBuilder> appResourceBuilder =
    resource => resource
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
        .AddProcessInstrumentation()
        .AddRuntimeInstrumentation()
        .AddAspNetCoreInstrumentation()
        .SetExemplarFilter(ExemplarFilterType.TraceBased)
        .AddOtlpExporter());
OpenFeature.Api.Instance.AddHooks(new TracingHook());
builder.Services.AddGrpc();
builder.Services.AddGrpcHealthChecks()
    .AddCheck("Sample", () => HealthCheckResult.Healthy());

var app = builder.Build();



app.MapGrpcService<CartService>();
app.MapGrpcHealthChecksService();

app.MapGet("/", async context =>
{
    await context.Response.WriteAsync("Communication with gRPC endpoints must be made through a gRPC client. To learn how to create a client, visit: https://go.microsoft.com/fwlink/?linkid=2086909");
});

app.Run();
