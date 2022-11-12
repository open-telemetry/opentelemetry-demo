// Copyright 2020 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

using Microsoft.AspNetCore.Hosting;
using Microsoft.Extensions.Hosting;
using Microsoft.AspNetCore.Builder;
using cartservice.cartstore;
using System;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Diagnostics.HealthChecks;
using OpenTelemetry.Metrics;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;
using cartservice.services;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using OpenTelemetry.Exporter;
using OpenTelemetry.Instrumentation.AspNetCore;
using OpenTelemetry.Logs;

var builder = WebApplication.CreateBuilder(args);

// log
using var loggerFactory = LoggerFactory.Create(builder =>
{
    builder.AddOpenTelemetry((opt) =>
    {
        opt.IncludeFormattedMessage = true;
        opt.IncludeScopes = true;
        opt.AddConsoleExporter();
    });
});

var logger = loggerFactory.CreateLogger<RedisCartStore>();

string redisAddress = builder.Configuration["REDIS_ADDR"];
RedisCartStore cartStore = null;
if (string.IsNullOrEmpty(redisAddress))
{
    logger.LogError("REDIS_ADDR environment variable is required.");
    System.Environment.Exit(1);
}
cartStore = new RedisCartStore(redisAddress,logger);

// Initialize the redis store
cartStore.InitializeAsync().GetAwaiter().GetResult();
logger.LogInformation("Initialization completed");

builder.Services.AddSingleton<ICartStore>(cartStore);

// tracing
builder.Services.AddOpenTelemetryTracing((builder) => builder
    .ConfigureResource(r => r.AddTelemetrySdk())
    .AddRedisInstrumentation(
        cartStore.GetConnection(),
        options => options.SetVerboseDatabaseStatements = true)
    .AddAspNetCoreInstrumentation()
    .AddGrpcClientInstrumentation()
    .AddHttpClientInstrumentation()
    .AddOtlpExporter());

// metric
builder.Services.AddOpenTelemetryMetrics(builder => builder
    .ConfigureResource(r => r.AddTelemetrySdk())
    .AddRuntimeInstrumentation()
    .AddAspNetCoreInstrumentation()
    .AddOtlpExporter());

// For options which can be bound from IConfiguration.
builder.Services.Configure<AspNetCoreInstrumentationOptions>(builder.Configuration.GetSection("AspNetCoreInstrumentation"));

builder.Services.AddGrpc();
builder.Services.AddGrpcHealthChecks()
    .AddCheck("Sample", () => HealthCheckResult.Healthy());

var app = builder.Build();

if (app.Environment.IsDevelopment())
        {
            app.UseDeveloperExceptionPage();
        }

app.UseRouting();

app.UseEndpoints(endpoints =>
{
    endpoints.MapGrpcService<CartService>();
    endpoints.MapGrpcHealthChecksService();

    endpoints.MapGet("/", async context =>
    {
        await context.Response.WriteAsync("Communication with gRPC endpoints must be made through a gRPC client. To learn how to create a client, visit: https://go.microsoft.com/fwlink/?linkid=2086909");
    });
});

app.Run();
