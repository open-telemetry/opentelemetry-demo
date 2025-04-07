// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
using System;
using System.Linq;
using System.Threading.Tasks;
using Grpc.Core;
using Google.Protobuf;
using Microsoft.Extensions.Logging;
using System.Diagnostics.Metrics;
using System.Diagnostics;
using Dapr.Client;
using Dapr.Common.Exceptions;
using Dapr;

namespace cart.cartstore;

public class DaprStateManagementCartStore : ICartStore
{
    private readonly ILogger _logger;
    private readonly string _daprStoreName;
    private DaprClient _client;
    private readonly byte[] _emptyCartBytes;
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

    public DaprStateManagementCartStore(ILogger<DaprStateManagementCartStore> logger, string daprStoreName)
    {
        _logger = logger;
        _daprStoreName = daprStoreName;
        // Serialize empty cart into byte array.
        var cart = new Oteldemo.Cart();
        _emptyCartBytes = cart.ToByteArray();
    }

    public void Initialize()
    {
        if (_client is null)
            _client = new DaprClientBuilder().Build();
    }

    public async Task AddItemAsync(string userId, string productId, int quantity)
    {
        var stopwatch = Stopwatch.StartNew();
        _logger.LogInformation("AddItemAsync called with userId={userId}, productId={productId}, quantity={quantity}", userId, productId, quantity);

        try
        {

            var value = await _client.GetStateAsync<byte[]>(_daprStoreName, userId.ToString());

            Oteldemo.Cart cart;
            if (value is null)
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
            await _client.SaveStateAsync(_daprStoreName, userId.ToString(), cart.ToByteArray());
        }
        catch (DaprException daprEx)
        {
            if (daprEx.TryGetExtendedErrorInfo(out DaprExtendedErrorInfo errorInfo))
            {

                 _logger.LogInformation("Dapr error: code: {errorInfo.Code} , message: {errorInfo.Message}", errorInfo.Code,errorInfo.Message);



                throw new RpcException(new Status(StatusCode.FailedPrecondition, $"Can't access cart storage. {daprEx}"));

            }
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
            await _client.SaveStateAsync(_daprStoreName, userId.ToString(), _emptyCartBytes);
        }
        catch (DaprException daprEx)
        {
            if (daprEx.TryGetExtendedErrorInfo(out DaprExtendedErrorInfo errorInfo))
            {

                 _logger.LogInformation("Dapr error: code: {errorInfo.Code} , message: {errorInfo.Message}", errorInfo.Code,errorInfo.Message);



                throw new RpcException(new Status(StatusCode.FailedPrecondition, $"Can't access cart storage. {daprEx}"));

            }
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

            // Access the cart from the cache
            var value = await _client.GetStateAsync<byte[]>(_daprStoreName, userId.ToString());

            if (value is not null)
            {
                return Oteldemo.Cart.Parser.ParseFrom(value);
            }

            // We decided to return empty cart in cases when user wasn't in the cache before
            return new Oteldemo.Cart();
        }
        catch (DaprException daprEx)
        {
            if (daprEx.TryGetExtendedErrorInfo(out DaprExtendedErrorInfo errorInfo))
            {

                 _logger.LogInformation("Dapr error: code: {errorInfo.Code} , message: {errorInfo.Message}", errorInfo.Code,errorInfo.Message);


                throw new RpcException(new Status(StatusCode.FailedPrecondition, $"Can't access cart storage. {daprEx}"));

            }
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
    public async Task<bool> Ping()
    {
        try
        {
            var isDaprReady = await _client.CheckHealthAsync();

            return isDaprReady;
        }
        catch (Exception)
        {
            return false;
        }
    }
    public async Task<bool> PingAsync()
    {
        return await _client.CheckOutboundHealthAsync();
    }
}
