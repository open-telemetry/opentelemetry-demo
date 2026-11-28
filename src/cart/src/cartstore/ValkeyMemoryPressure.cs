// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
using System;
using System.Globalization;
using System.Linq;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using StackExchange.Redis;

namespace cart.cartstore;

internal static class ValkeyMemoryPressure
{
    private const string RecoveryKey = "otel-demo:cart:valkey-memory-pressure";
    private const long MemoryPressureMarginBytes = 30_000;

    internal static async Task ReconcileAsync(
        IServer server, IDatabase database, bool enabled, ILogger logger, CancellationToken cancellationToken)
    {
        var storedSettings = await database.StringGetAsync(RecoveryKey);
        if (!enabled && storedSettings.IsNull)
        {
            return;
        }

        var serverInfo = await server.InfoAsync("server");
        var runId = serverInfo.SelectMany(section => section).First(kv => kv.Key == "run_id").Value;
        var originalSettings = storedSettings.IsNull
            ? null
            : JsonSerializer.Deserialize<MemorySettings>(storedSettings.ToString())
                ?? throw new InvalidOperationException("Missing saved Valkey memory settings.");

        cancellationToken.ThrowIfCancellationRequested();
        if (originalSettings is not null && originalSettings.RunId != runId)
        {
            await database.KeyDeleteAsync(RecoveryKey);
            originalSettings = null;
        }

        if (!enabled)
        {
            if (originalSettings is not null)
            {
                await server.ConfigSetAsync("maxmemory", originalSettings.MaxMemory);
                await server.ConfigSetAsync("maxmemory-policy", originalSettings.EvictionPolicy);
                await database.KeyDeleteAsync(RecoveryKey);
                Log.ValkeyMemoryPressureDisabled(logger);
            }

            return;
        }

        var maxMemory = long.Parse((await server.ConfigGetAsync("maxmemory"))[0].Value, CultureInfo.InvariantCulture);
        var memoryInfo = (await server.InfoAsync("memory")).SelectMany(section => section);
        var usedMemory = long.Parse(
            memoryInfo.First(kv => kv.Key == "used_memory").Value,
            CultureInfo.InvariantCulture);
        var excludedMemory = long.Parse(
            memoryInfo.FirstOrDefault(kv => kv.Key == "mem_not_counted_for_evict").Value ?? "0",
            CultureInfo.InvariantCulture);
        var countedMemory = Math.Max(0, usedMemory - excludedMemory);
        if (maxMemory > 0 && countedMemory > maxMemory)
        {
            return;
        }

        var policy = (await server.ConfigGetAsync("maxmemory-policy"))[0].Value;
        cancellationToken.ThrowIfCancellationRequested();
        if (originalSettings is null)
        {
            storedSettings = JsonSerializer.Serialize(new MemorySettings(runId, maxMemory, policy));
            if (!await database.StringSetAsync(RecoveryKey, storedSettings, when: ValueCondition.NotExists))
            {
                return;
            }
        }

        if (policy != "noeviction")
        {
            var transaction = database.CreateTransaction();
            transaction.AddCondition(Condition.StringEqual(RecoveryKey, storedSettings));
            var setPolicy = transaction.ExecuteAsync("CONFIG", "SET", "maxmemory-policy", "noeviction");
            if (!await transaction.ExecuteAsync())
            {
                return;
            }

            await setPolicy;
        }

        var newMaxMemory = Math.Max(1, countedMemory - MemoryPressureMarginBytes);
        await server.ConfigSetAsync("maxmemory", newMaxMemory);
        Log.ValkeyMemoryPressureEnabled(logger);
    }

    private sealed record MemorySettings(string RunId, long MaxMemory, string EvictionPolicy);
}
