// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using cart.cartstore;
using Microsoft.Extensions.Logging.Abstractions;
using StackExchange.Redis;
using Xunit;

namespace cart.tests;

public class ValkeyMemoryPressureTests
{
    [Theory]
    [InlineData(0L, "noeviction")]
    [InlineData(200_000L, "allkeys-lru")]
    public async Task Off_RestoresSettingsAfterUsageFalls(long originalLimit, string originalPolicy)
    {
        var valkey = new StubValkey { MaxMemory = originalLimit, EvictionPolicy = originalPolicy };
        await valkey.ReconcileAsync(enabled: true);
        Assert.Equal(70_000, valkey.MaxMemory);
        Assert.Equal("noeviction", valkey.EvictionPolicy);

        valkey.UsedMemory = 60_000;
        await valkey.ReconcileAsync(enabled: true);
        Assert.Equal(30_000, valkey.MaxMemory);

        valkey.UsedMemory = 25_000;
        await valkey.ReconcileAsync(enabled: false);

        Assert.Equal(originalLimit, valkey.MaxMemory);
        Assert.Equal(originalPolicy, valkey.EvictionPolicy);
        Assert.False(valkey.HasSavedSettings);
    }

    [Fact]
    public async Task Off_PreservesAnExistingLimitWithoutSavedSettings()
    {
        var valkey = new StubValkey { MaxMemory = 70_000, EvictionPolicy = "allkeys-lru" };

        await valkey.ReconcileAsync(enabled: false);

        Assert.Equal(70_000, valkey.MaxMemory);
        Assert.Equal("allkeys-lru", valkey.EvictionPolicy);
        Assert.Equal(0, valkey.ConfigurationWrites);
    }

    [Fact]
    public async Task Off_RetriesAnIncompleteRestore()
    {
        var valkey = new StubValkey { MaxMemory = 200_000, EvictionPolicy = "allkeys-lru" };
        await valkey.ReconcileAsync(enabled: true);
        valkey.FailNextPolicyWrite = true;

        await Assert.ThrowsAsync<TimeoutException>(() => valkey.ReconcileAsync(enabled: false));
        Assert.Equal(200_000, valkey.MaxMemory);
        Assert.Equal("noeviction", valkey.EvictionPolicy);
        Assert.True(valkey.HasSavedSettings);

        await valkey.ReconcileAsync(enabled: false);

        Assert.Equal("allkeys-lru", valkey.EvictionPolicy);
        Assert.False(valkey.HasSavedSettings);
    }

    [Fact]
    public async Task Off_DiscardsSettingsFromAnEarlierValkeyRun()
    {
        var valkey = new StubValkey { MaxMemory = 200_000, EvictionPolicy = "allkeys-lru" };
        await valkey.ReconcileAsync(enabled: true);
        valkey.RunId = "restarted";
        valkey.MaxMemory = 90_000;
        valkey.EvictionPolicy = "allkeys-lfu";
        var configurationWrites = valkey.ConfigurationWrites;

        await valkey.ReconcileAsync(enabled: false);

        Assert.Equal(90_000, valkey.MaxMemory);
        Assert.Equal("allkeys-lfu", valkey.EvictionPolicy);
        Assert.Equal(configurationWrites, valkey.ConfigurationWrites);
        Assert.False(valkey.HasSavedSettings);
    }

    [Fact]
    public async Task On_PreservesSettingsIfRecoveryRecordIsEvicted()
    {
        var valkey = new StubValkey
        {
            MaxMemory = 200_000,
            EvictionPolicy = "allkeys-lru",
            EvictSavedSettingsBeforePolicySwitch = true,
        };

        await valkey.ReconcileAsync(enabled: true);

        Assert.Equal(200_000, valkey.MaxMemory);
        Assert.Equal("allkeys-lru", valkey.EvictionPolicy);
        Assert.Equal(0, valkey.ConfigurationWrites);
    }

    [Fact]
    public async Task On_BasesTheCapOnMemoryCountedForEviction()
    {
        var valkey = new StubValkey
        {
            UsedMemory = 125_000,
            MemoryExcludedFromEviction = 55_000,
        };

        await valkey.ReconcileAsync(enabled: true);

        Assert.Equal(40_000, valkey.MaxMemory);
    }

    [Fact]
    public async Task On_ReappliesTheCapAfterCountedMemoryDrops()
    {
        var valkey = new StubValkey { UsedMemory = 170_000 };
        await valkey.ReconcileAsync(enabled: true);
        Assert.Equal(140_000, valkey.MaxMemory);

        valkey.UsedMemory = 210_000;
        valkey.MemoryExcludedFromEviction = 90_000;
        await valkey.ReconcileAsync(enabled: true);

        Assert.Equal(90_000, valkey.MaxMemory);
    }

    private sealed class StubValkey
    {
        private readonly IServer _server;
        private readonly IDatabase _database;
        private RedisValue _savedSettings = RedisValue.Null;

        public StubValkey()
        {
            _server = RedisProxy.Create<IServer>(InvokeServer);
            _database = RedisProxy.Create<IDatabase>(InvokeDatabase);
        }

        public long MaxMemory { get; set; }
        public long UsedMemory { get; set; } = 100_000;
        public long? MemoryExcludedFromEviction { get; set; }
        public string EvictionPolicy { get; set; } = "noeviction";
        public string RunId { get; set; } = "initial";
        public bool FailNextPolicyWrite { get; set; }
        public bool EvictSavedSettingsBeforePolicySwitch { get; set; }
        public int ConfigurationWrites { get; private set; }
        public bool HasSavedSettings => !_savedSettings.IsNull;

        public Task ReconcileAsync(bool enabled) => ValkeyMemoryPressure.ReconcileAsync(
            _server, _database, enabled, NullLogger.Instance, TestContext.Current.CancellationToken);

        private object InvokeServer(MethodInfo method, object?[] args)
        {
            var parameter = ((RedisValue)args[0]!).ToString();
            return method.Name switch
            {
                nameof(IServer.InfoAsync) when parameter == "server" => Info(parameter, KeyValuePair.Create("run_id", RunId)),
                nameof(IServer.InfoAsync) when parameter == "memory" => MemoryInfo(),
                nameof(IServer.ConfigGetAsync) when parameter == "maxmemory" => Task.FromResult(
                    new[] { KeyValuePair.Create(parameter, MaxMemory.ToString(CultureInfo.InvariantCulture)) }),
                nameof(IServer.ConfigGetAsync) when parameter == "maxmemory-policy" => Task.FromResult(
                    new[] { KeyValuePair.Create(parameter, EvictionPolicy) }),
                nameof(IServer.ConfigSetAsync) => SetConfigAsync(parameter, (RedisValue)args[1]!),
                _ => throw new NotSupportedException(method.Name),
            };
        }

        private static Task<IGrouping<string, KeyValuePair<string, string>>[]> Info(
            string section, params KeyValuePair<string, string>[] values) =>
            Task.FromResult(values.GroupBy(_ => section).ToArray());

        private Task<IGrouping<string, KeyValuePair<string, string>>[]> MemoryInfo()
        {
            var usedMemory = KeyValuePair.Create("used_memory", UsedMemory.ToString(CultureInfo.InvariantCulture));
            return MemoryExcludedFromEviction is long excludedMemory
                ? Info("memory", usedMemory, KeyValuePair.Create(
                    "mem_not_counted_for_evict", excludedMemory.ToString(CultureInfo.InvariantCulture)))
                : Info("memory", usedMemory);
        }

        private Task SetConfigAsync(string parameter, RedisValue value)
        {
            ConfigurationWrites++;
            if (parameter == "maxmemory")
            {
                MaxMemory = (long)value;
            }
            else if (FailNextPolicyWrite)
            {
                FailNextPolicyWrite = false;
                return Task.FromException(new TimeoutException());
            }
            else
            {
                EvictionPolicy = value.ToString();
            }

            return Task.CompletedTask;
        }

        private object InvokeDatabase(MethodInfo method, object?[] args)
        {
            switch (method.Name)
            {
                case nameof(IDatabase.StringGetAsync):
                    return Task.FromResult(_savedSettings);
                case nameof(IDatabase.StringSetAsync):
                    Assert.Equal(ValueCondition.NotExists, Assert.IsType<ValueCondition>(args[3]));
                    if (HasSavedSettings)
                    {
                        return Task.FromResult(false);
                    }

                    _savedSettings = (RedisValue)args[1]!;
                    return Task.FromResult(true);
                case nameof(IDatabase.KeyDeleteAsync):
                    var deleted = HasSavedSettings;
                    _savedSettings = RedisValue.Null;
                    return Task.FromResult(deleted);
                case nameof(IDatabase.CreateTransaction):
                    return CreatePolicyTransaction();
                default:
                    throw new NotSupportedException(method.Name);
            }
        }

        private ITransaction CreatePolicyTransaction()
        {
            var conditionAdded = false;
            string? pendingPolicy = null;
            return RedisProxy.Create<ITransaction>((method, args) =>
            {
                switch (method.Name)
                {
                    case nameof(ITransaction.AddCondition):
                        conditionAdded = true;
                        return null;
                    case nameof(ITransaction.ExecuteAsync) when args[0] is string:
                        Assert.Equal("CONFIG", args[0]);
                        var command = Assert.IsType<object[]>(args[1]);
                        Assert.Equal("SET", command[0]);
                        Assert.Equal("maxmemory-policy", command[1]);
                        pendingPolicy = Assert.IsType<string>(command[2]);
                        return Task.FromResult<RedisResult>(null!);
                    case nameof(ITransaction.ExecuteAsync):
                        Assert.True(conditionAdded);
                        if (EvictSavedSettingsBeforePolicySwitch)
                        {
                            _savedSettings = RedisValue.Null;
                        }

                        if (!HasSavedSettings)
                        {
                            return Task.FromResult(false);
                        }

                        EvictionPolicy = Assert.IsType<string>(pendingPolicy);
                        ConfigurationWrites++;
                        return Task.FromResult(true);
                    default:
                        throw new NotSupportedException(method.Name);
                }
            });
        }
    }

    public class RedisProxy : DispatchProxy
    {
        private Func<MethodInfo, object?[], object?> _invoke = null!;

        public static T Create<T>(Func<MethodInfo, object?[], object?> invoke) where T : class
        {
            var proxy = Create<T, RedisProxy>();
            ((RedisProxy)(object)proxy)._invoke = invoke;
            return proxy;
        }

        protected override object? Invoke(MethodInfo? targetMethod, object?[]? args) => _invoke(targetMethod!, args!);
    }
}
