// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using System;
using Microsoft.Extensions.Logging;

namespace cart;

internal static partial class Log
{
    [LoggerMessage(Level = LogLevel.Debug, EventName = "cart.redis.connecting", Message = "Connecting to Redis: {connectionString}")]
    public static partial void RedisConnecting(ILogger logger, string connectionString);

    [LoggerMessage(Level = LogLevel.Error, EventName = "cart.redis.connection_failed", Message = "Wasn't able to connect to redis")]
    public static partial void RedisConnectionFailed(ILogger logger);

    [LoggerMessage(Level = LogLevel.Information, EventName = "cart.redis.connected", Message = "Successfully connected to Redis")]
    public static partial void RedisConnected(ILogger logger);

    [LoggerMessage(Level = LogLevel.Debug, EventName = "cart.redis.small_test", Message = "Performing small test")]
    public static partial void RedisSmallTest(ILogger logger);

    [LoggerMessage(Level = LogLevel.Debug, EventName = "cart.redis.small_test_result", Message = "Small test result: {result}")]
    public static partial void RedisSmallTestResult(ILogger logger, string result);

    [LoggerMessage(Level = LogLevel.Information, EventName = "cart.redis.connection_restored", Message = "Connection to redis was restored successfully.")]
    public static partial void RedisConnectionRestored(ILogger logger);

    [LoggerMessage(Level = LogLevel.Information, EventName = "cart.redis.connection_lost", Message = "Connection failed. Disposing the object")]
    public static partial void RedisConnectionLost(ILogger logger);

    [LoggerMessage(Level = LogLevel.Error, EventName = "cart.redis.internal_error", Message = "Redis internal error")]
    public static partial void RedisInternalError(ILogger logger, Exception exception);

    [LoggerMessage(Level = LogLevel.Information, EventName = "cart.add_item", Message = "AddItemAsync called with userId={userId}, productId={productId}, quantity={quantity}")]
    public static partial void AddItemAsync(ILogger logger, string userId, string productId, int quantity);

    [LoggerMessage(Level = LogLevel.Information, EventName = "cart.empty", Message = "EmptyCartAsync called with userId={userId}")]
    public static partial void EmptyCartAsync(ILogger logger, string userId);

    [LoggerMessage(Level = LogLevel.Information, EventName = "cart.get", Message = "GetCartAsync called with userId={userId}")]
    public static partial void GetCartAsync(ILogger logger, string userId);

    [LoggerMessage(Level = LogLevel.Information, EventName = "cart.health_check.request", Message = "Received health check request for service: {service}")]
    public static partial void HealthCheckRequest(ILogger logger, string service);

    [LoggerMessage(Level = LogLevel.Information, EventName = "cart.health_watch.request", Message = "Received health watch request for service: {service}")]
    public static partial void HealthWatchRequest(ILogger logger, string service);
}
