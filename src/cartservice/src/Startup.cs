using System;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Diagnostics.HealthChecks;
using Microsoft.Extensions.Hosting;
using cartservice.cartstore;
using cartservice.services;
using OpenTelemetry.Metrics;
using OpenTelemetry.Trace;

namespace cartservice;

public class Startup
{
    public Startup(IConfiguration configuration)
    {
        Configuration = configuration;
    }

    public IConfiguration Configuration { get; }

    // This method gets called by the runtime. Use this method to add services to the container.
    // For more information on how to configure your application, visit https://go.microsoft.com/fwlink/?LinkID=398940
    public void ConfigureServices(IServiceCollection services)
    {
        string redisAddress = Configuration["REDIS_ADDR"];
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

        services.AddSingleton<ICartStore>(cartStore);

        services.AddOpenTelemetryTracing((builder) => builder
            .AddRedisInstrumentation(
                cartStore.GetConnection(),
                options => options.SetVerboseDatabaseStatements = true)
            .AddAspNetCoreInstrumentation()
            .AddGrpcClientInstrumentation()
            .AddHttpClientInstrumentation()
            .AddOtlpExporter());

            services.AddOpenTelemetryMetrics(builder =>
                builder.AddRuntimeInstrumentation()
                       .AddOtlpExporter());

        services.AddGrpc();
        services.AddGrpcHealthChecks()
            .AddCheck("Sample", () => HealthCheckResult.Healthy());
    }

    // This method gets called by the runtime. Use this method to configure the HTTP request pipeline.
    public void Configure(IApplicationBuilder app, IWebHostEnvironment env)
    {
        if (env.IsDevelopment())
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
    }
}
