// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
using System;
using System.Threading;
using System.Threading.Tasks;
using cart.cartstore;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace cart.services;

internal sealed class ValkeyMemoryPressureService(ValkeyCartStore cartStore, ILogger<ValkeyCartStore> logger) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        using var timer = new PeriodicTimer(TimeSpan.FromSeconds(5));
        do
        {
            stoppingToken.ThrowIfCancellationRequested();
            try
            {
                await cartStore.ReconcileMemoryPressureAsync(stoppingToken);
            }
            catch (Exception ex) when (ex is not OperationCanceledException || !stoppingToken.IsCancellationRequested)
            {
                Log.ValkeyMemoryPressureFailed(logger, ex);
            }
        } while (await timer.WaitForNextTickAsync(stoppingToken));
    }
}
