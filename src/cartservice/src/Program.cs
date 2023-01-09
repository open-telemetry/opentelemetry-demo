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
using OpenTelemetry.Extensions.Docker.Resources;
using OpenTelemetry.Trace;
using cartservice.services;
using Microsoft.AspNetCore.Http;

var builder = WebApplication.CreateBuilder(args);
string redisAddress = builder.Configuration["REDIS_ADDR"];
RedisCartStore cartStore = null;
if (string.IsNullOrEmpty(redisAddress))
{
    Console.WriteLine("REDIS_ADDR environment variable is required.");
    System.Environment.Exit(1);
}
cartStore = new RedisCartStore(redisAddress);

// Initialize the redis store
cartStore.InitializeAsync().GetAwaiter().GetResult();
Console.WriteLine("Initialization completed");

builder.Services.AddSingleton<ICartStore>(cartStore);

builder.Services.AddOpenTelemetryTracing((builder) => builder
    .ConfigureResource(r => r
        .AddTelemetrySdk()
        .AddEnvironmentVariableDetector()
        .AddDetector(new DockerResourceDetector())
    )
    .AddRedisInstrumentation(
        cartStore.GetConnection(),
        options => options.SetVerboseDatabaseStatements = true)
    .AddAspNetCoreInstrumentation()
    .AddGrpcClientInstrumentation()
    .AddHttpClientInstrumentation()
    .AddOtlpExporter());

builder.Services.AddOpenTelemetryMetrics(builder => builder
    .ConfigureResource(r => r
        .AddTelemetrySdk()
        .AddEnvironmentVariableDetector()
        .AddDetector(new DockerResourceDetector())
    )
    .AddRuntimeInstrumentation()
    .AddAspNetCoreInstrumentation()
    .AddOtlpExporter());

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
