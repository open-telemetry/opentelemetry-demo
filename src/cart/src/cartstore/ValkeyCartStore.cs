// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
using System;
using System.Linq;
using System.Threading.Tasks;
using Grpc.Core;
using StackExchange.Redis;
using Google.Protobuf;
using Microsoft.Extensions.Logging;
using System.Diagnostics.Metrics;
using System.Diagnostics;
using System.Threading;

namespace cart.cartstore;

public class ValkeyCartStore : ICartStore
{
    private readonly ILogger _logger;
    private const string CartFieldName = "cart";
    private const int RedisRetryNumber = 30;
    private const int CartMutationMaxAttempts = 30;

    private volatile ConnectionMultiplexer _redis;
    private volatile bool _isRedisConnectionOpened;

    private readonly Lock _locker = new();
    private readonly byte[] _emptyCartBytes;
    private readonly string _connectionString;

    private static readonly ActivitySource CartActivitySource = new("OpenTelemetry.Demo.Cart");
    private static readonly Meter CartMeter = new Meter("OpenTelemetry.Demo.Cart");
    private static readonly Histogram<double> addItemHistogram = CartMeter.CreateHistogram(
        "demo.cart.add_item.latency",
        unit: "s",
        advice: new InstrumentAdvice<double>
        {
            HistogramBucketBoundaries = [ 0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1, 2.5, 5, 7.5, 10 ]
        });
    private static readonly Histogram<double> getCartHistogram = CartMeter.CreateHistogram(
        "demo.cart.get_cart.latency",
        unit: "s",
        advice: new InstrumentAdvice<double>
        {
            HistogramBucketBoundaries = [ 0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1, 2.5, 5, 7.5, 10 ]
        });
    private readonly ConfigurationOptions _redisConnectionOptions;

    public ValkeyCartStore(ILogger<ValkeyCartStore> logger, string valkeyAddress)
    {
        _logger = logger;
        // Serialize empty cart into byte array.
        var cart = new Oteldemo.Cart();
        _emptyCartBytes = cart.ToByteArray();
        _connectionString = $"{valkeyAddress},ssl=false,allowAdmin=true,abortConnect=false";

        _redisConnectionOptions = ConfigurationOptions.Parse(_connectionString);

        // Try to reconnect multiple times if the first retry fails.
        _redisConnectionOptions.ConnectRetry = RedisRetryNumber;
        _redisConnectionOptions.ReconnectRetryPolicy = new ExponentialRetry(1000);

        _redisConnectionOptions.KeepAlive = 180;
    }

    public ConnectionMultiplexer GetConnection()
    {
        EnsureRedisConnected();
        return _redis;
    }

    public void Initialize()
    {
        EnsureRedisConnected();
    }

    private void EnsureRedisConnected()
    {
        if (_isRedisConnectionOpened)
        {
            return;
        }

        // Connection is closed or failed - open a new one but only at the first thread
        lock (_locker)
        {
            if (_isRedisConnectionOpened)
            {
                return;
            }

            Log.RedisConnecting(_logger, _connectionString);

            _redis = ConnectionMultiplexer.Connect(_redisConnectionOptions);

            if (_redis == null || !_redis.IsConnected)
            {
                Log.RedisConnectionFailed(_logger);

                // We weren't able to connect to Redis despite some retries with exponential backoff.
                throw new ApplicationException("Wasn't able to connect to redis");
            }

            Log.RedisConnected(_logger);
            var cache = _redis.GetDatabase();

            Log.RedisSmallTest(_logger);
            cache.StringSet("cart", "OK" );
            string res = (string)cache.StringGet("cart");

            Log.RedisSmallTestResult(_logger, res);

            _redis.InternalError += (_, e) => { Log.RedisInternalError(_logger, e.Exception); };
            _redis.ConnectionRestored += (_, _) =>
            {
                _isRedisConnectionOpened = true;
                Log.RedisConnectionRestored(_logger);
            };
            _redis.ConnectionFailed += (_, _) =>
            {
                Log.RedisConnectionLost(_logger);
                _isRedisConnectionOpened = false;
            };

            _isRedisConnectionOpened = true;
        }
    }

    public async Task AddItemAsync(string userId, string productId, int quantity)
    {
        var stopwatch = Stopwatch.StartNew();

        Log.AddItemAsync(_logger, userId, productId, quantity);

        try
        {
            await MutateCartAsync(userId, cart =>
            {
                var existingItem = cart.Items.SingleOrDefault(i => i.ProductId == productId);
                if (existingItem == null)
                {
                    // A negative delta for a product that isn't in the cart has nothing to remove.
                    if (quantity > 0)
                    {
                        cart.Items.Add(new Oteldemo.CartItem { ProductId = productId, Quantity = quantity });
                    }
                    return;
                }

                existingItem.Quantity += quantity;
                if (existingItem.Quantity <= 0)
                {
                    cart.Items.Remove(existingItem);
                }
            });
        }
        catch (RpcException)
        {
            throw;
        }
        catch (Exception ex)
        {
            throw new RpcException(new Status(StatusCode.FailedPrecondition, $"Can't access cart storage. {ex}"));
        }
        finally
        {
            addItemHistogram.Record(stopwatch.Elapsed.TotalSeconds);
        }
    }

    // Applies `mutate` to the user's current cart and writes it back with an optimistic-concurrency
    // check (Redis transaction conditioned on the hash field still matching what we just read), retrying
    // on conflict. This closes the lost-update window that a plain read -> modify -> write sequence has
    // when two callers mutate the same cart concurrently.
    private async Task MutateCartAsync(string userId, Action<Oteldemo.Cart> mutate)
    {
        EnsureRedisConnected();

        var db = _redis.GetDatabase();

        for (var attempt = 0; attempt < CartMutationMaxAttempts; attempt++)
        {
            var existingValue = await db.HashGetAsync(userId, CartFieldName);

            var cart = existingValue.IsNull
                ? new Oteldemo.Cart { UserId = userId }
                : Oteldemo.Cart.Parser.ParseFrom((byte[])existingValue);

            mutate(cart);

            var transaction = db.CreateTransaction();
            transaction.AddCondition(existingValue.IsNull
                ? Condition.HashNotExists(userId, CartFieldName)
                : Condition.HashEqual(userId, CartFieldName, existingValue));

            _ = transaction.HashSetAsync(userId, new[] { new HashEntry(CartFieldName, cart.ToByteArray()) });
            _ = transaction.KeyExpireAsync(userId, TimeSpan.FromMinutes(60));

            if (await transaction.ExecuteAsync())
            {
                return;
            }

            // Another writer changed the cart between our read and write. Back off briefly with jitter
            // so a burst of concurrent writers to the same cart doesn't keep colliding in lockstep.
            await Task.Delay(Random.Shared.Next(2, 10) * (attempt + 1));
        }

        throw new RpcException(new Status(StatusCode.Aborted,
            $"Couldn't update cart for user {userId} after {CartMutationMaxAttempts} attempts due to concurrent modifications."));
    }

    public async Task EmptyCartAsync(string userId)
    {
        Log.EmptyCartAsync(_logger, userId);
        try
        {
            EnsureRedisConnected();
            var db = _redis.GetDatabase();

            // Update the cache with empty cart for given user
            await db.HashSetAsync(userId, new[] { new HashEntry(CartFieldName, _emptyCartBytes) });
            await db.KeyExpireAsync(userId, TimeSpan.FromMinutes(60));
        }
        catch (Exception ex)
        {
            throw new RpcException(new Status(StatusCode.FailedPrecondition, $"Can't access cart storage. {ex}"));
        }
    }

    public async Task<Oteldemo.Cart> GetCartAsync(string userId)
    {
        var stopwatch = Stopwatch.StartNew();

        Log.GetCartAsync(_logger, userId);

        try
        {
            EnsureRedisConnected();

            var db = _redis.GetDatabase();

            // Access the cart from the cache
            var value = await db.HashGetAsync(userId, CartFieldName);

            if (!value.IsNull)
            {
                return Oteldemo.Cart.Parser.ParseFrom((byte[])value);
            }

            // We decided to return empty cart in cases when user wasn't in the cache before
            return new Oteldemo.Cart();
        }
        catch (Exception ex)
        {
            throw new RpcException(new Status(StatusCode.FailedPrecondition, $"Can't access cart storage. {ex}"));
        }
        finally
        {
            getCartHistogram.Record(stopwatch.Elapsed.TotalSeconds);
        }
    }

    public bool Ping()
    {
        try
        {
            var cache = _redis.GetDatabase();
            var res = cache.Ping();
            return res != TimeSpan.Zero;
        }
        catch (Exception)
        {
            return false;
        }
    }
}
