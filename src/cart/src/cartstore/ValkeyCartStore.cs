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

namespace cart.cartstore;

public class ValkeyCartStore : ICartStore
{
    private readonly ILogger _logger;
    private const string CartFieldName = "cart";
    private const int RedisRetryNumber = 30;

    private volatile ConnectionMultiplexer _redis;
    private volatile bool _isRedisConnectionOpened;

    private readonly object _locker = new();
    private readonly byte[] _emptyCartBytes;
    private readonly string _connectionString;

    private static readonly ActivitySource CartActivitySource = new("OpenTelemetry.Demo.Cart");
    private static readonly Meter CartMeter = new Meter("OpenTelemetry.Demo.Cart");
    private static readonly Histogram<long> addItemHistogram = CartMeter.CreateHistogram<long>(
        "app.cart.add_item.latency",
        advice: new InstrumentAdvice<long>
        {
            HistogramBucketBoundaries = [ 500000, 600000, 700000, 800000, 900000, 1000000, 1100000 ]
        });
    private static readonly Histogram<long> getCartHistogram = CartMeter.CreateHistogram<long>(
        "app.cart.get_cart.latency",
        advice: new InstrumentAdvice<long>
        {
            HistogramBucketBoundaries = [ 300000, 400000, 500000, 600000, 700000, 800000, 900000 ]
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

            _logger.LogDebug("Connecting to Redis: {_connectionString}", _connectionString);
            _redis = ConnectionMultiplexer.Connect(_redisConnectionOptions);

            if (_redis == null || !_redis.IsConnected)
            {
                _logger.LogError("Wasn't able to connect to redis");

                // We weren't able to connect to Redis despite some retries with exponential backoff.
                throw new ApplicationException("Wasn't able to connect to redis");
            }

            _logger.LogInformation("Successfully connected to Redis");
            var cache = _redis.GetDatabase();

            _logger.LogDebug("Performing small test");
            cache.StringSet("cart", "OK" );
            object res = cache.StringGet("cart");
            _logger.LogDebug("Small test result: {res}", res);

            _redis.InternalError += (_, e) => { Console.WriteLine(e.Exception); };
            _redis.ConnectionRestored += (_, _) =>
            {
                _isRedisConnectionOpened = true;
                _logger.LogInformation("Connection to redis was restored successfully.");
            };
            _redis.ConnectionFailed += (_, _) =>
            {
                _logger.LogInformation("Connection failed. Disposing the object");
                _isRedisConnectionOpened = false;
            };

            _isRedisConnectionOpened = true;
        }
    }

    public async Task AddItemAsync(string userId, string productId, int quantity)
    {
        var stopwatch = Stopwatch.StartNew();
        _logger.LogInformation("AddItemAsync called with userId={userId}, productId={productId}, quantity={quantity}", userId, productId, quantity);

        try
        {
            EnsureRedisConnected();

            var db = _redis.GetDatabase();

            // Access the cart from the cache
            var value = await db.HashGetAsync(userId, CartFieldName);

            Oteldemo.Cart cart;
            if (value.IsNull)
            {
                cart = new Oteldemo.Cart
                {
                    UserId = userId
                };
                cart.Items.Add(new Oteldemo.CartItem { ProductId = productId, Quantity = quantity });
            }
            else
            {
                cart = Oteldemo.Cart.Parser.ParseFrom(value);
                var existingItem = cart.Items.SingleOrDefault(i => i.ProductId == productId);
                if (existingItem == null)
                {
                    cart.Items.Add(new Oteldemo.CartItem { ProductId = productId, Quantity = quantity });
                }
                else
                {
                    existingItem.Quantity += quantity;
                }
            }

            await db.HashSetAsync(userId, new[]{ new HashEntry(CartFieldName, cart.ToByteArray()) });
            await db.KeyExpireAsync(userId, TimeSpan.FromMinutes(60));
        }
        catch (Exception ex)
        {
            throw new RpcException(new Status(StatusCode.FailedPrecondition, $"Can't access cart storage. {ex}"));
        }
        finally
        {
            addItemHistogram.Record(stopwatch.ElapsedTicks);
        }
    }

    public async Task EmptyCartAsync(string userId)
    {
        _logger.LogInformation("EmptyCartAsync called with userId={userId}", userId);

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
        _logger.LogInformation("GetCartAsync called with userId={userId}", userId);

        try
        {
            EnsureRedisConnected();

            var db = _redis.GetDatabase();

            // Access the cart from the cache
            var value = await db.HashGetAsync(userId, CartFieldName);

            if (!value.IsNull)
            {
                return Oteldemo.Cart.Parser.ParseFrom(value);
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
            getCartHistogram.Record(stopwatch.ElapsedTicks);
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
