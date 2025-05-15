// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using Accounting;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using OpenTelemetry;
using OpenTelemetry.Trace;

Console.WriteLine("Accounting service started");

Environment.GetEnvironmentVariables()
    .FilterRelevant()
    .OutputInOrder();

var tracerProvider = Sdk.CreateTracerProviderBuilder()
    .AddEntityFrameworkCoreInstrumentation()
    .AddConsoleExporter()
    .AddSource("Accounting.Consumer")
    .Build();

var host = Host.CreateDefaultBuilder(args)
    .ConfigureServices(services =>
    {
        services.AddSingleton<Consumer>();
    })
    .Build();

var consumer = host.Services.GetRequiredService<Consumer>();
consumer.StartListening();

host.Run();
