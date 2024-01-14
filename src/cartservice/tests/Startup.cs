using cartservice.cartstore;
using cartservice.services;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Diagnostics.HealthChecks;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using OpenTelemetry.Instrumentation.StackExchangeRedis;
using OpenTelemetry.Logs;
using OpenTelemetry.Metrics;
using OpenTelemetry.ResourceDetectors.Container;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;
using System;

namespace cartservice.tests;

internal class Startup(IConfiguration configuration)
{
    public IConfiguration Configuration { get; } = configuration;

    public void ConfigureServices(IServiceCollection services)
    {
        string redisAddress = Configuration["REDIS_ADDR"];
        if (string.IsNullOrEmpty(redisAddress))
        {
            throw new InvalidOperationException("REDIS_ADDR environment variable is required.");
        }

        services.AddLogging(builder => builder.AddOpenTelemetry(options => options.AddOtlpExporter()).AddConsole());

        services.AddSingleton<ICartStore>(x =>
        {
            var store = new RedisCartStore(x.GetRequiredService<ILogger<RedisCartStore>>(), redisAddress);
            store.Initialize();
            return store;
        });

        // see https://opentelemetry.io/docs/instrumentation/net/getting-started/

        Action<ResourceBuilder> appResourceBuilder =
            resource => resource
                .AddDetector(new ContainerResourceDetector());

        services.AddOpenTelemetry()
            .ConfigureResource(appResourceBuilder)
            .WithTracing(tracerBuilder => tracerBuilder
                .AddRedisInstrumentation(
                    options => options.SetVerboseDatabaseStatements = true)
                .AddAspNetCoreInstrumentation()
                .AddGrpcClientInstrumentation()
                .AddHttpClientInstrumentation()
                .AddOtlpExporter())
            .WithMetrics(meterBuilder => meterBuilder
                .AddProcessInstrumentation()
                .AddRuntimeInstrumentation()
                .AddAspNetCoreInstrumentation()
                .AddOtlpExporter());

        services.AddGrpc();
        services.AddGrpcHealthChecks()
            .AddCheck("Sample", () => HealthCheckResult.Healthy());
    }

    public void Configure(IApplicationBuilder app, IWebHostEnvironment env)
    {
        if (env.IsDevelopment())
        {
            app.UseDeveloperExceptionPage();
        }

        app.UseRouting();

        app.UseEndpoints(endpoints =>
        {
            var redisCartStore = (RedisCartStore)app.ApplicationServices.GetRequiredService<ICartStore>();
            app.ApplicationServices.GetRequiredService<StackExchangeRedisInstrumentation>().AddConnection(redisCartStore.GetConnection());

            endpoints.MapGrpcService<CartService>();
            endpoints.MapGrpcHealthChecksService();
            endpoints.MapGet("/", async context =>
            {
                await context.Response.WriteAsync("Communication with gRPC endpoints must be made through a gRPC client. To learn how to create a client, visit: https://go.microsoft.com/fwlink/?linkid=2086909");
            });
        });
    }
}
