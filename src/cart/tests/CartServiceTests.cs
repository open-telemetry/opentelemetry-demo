// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Grpc.Net.Client;
using Oteldemo;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging.Abstractions;
using OpenFeature;
using Xunit;
using cart.cartstore;
using static Oteldemo.CartService;

namespace cart.tests;

public class CartServiceTests
{
    private readonly IHostBuilder _host;

    public CartServiceTests()
    {
        var valkeyAddress = Environment.GetEnvironmentVariable("VALKEY_ADDR") ?? "localhost:6379";

        _host = new HostBuilder().ConfigureWebHost(webBuilder =>
        {
            webBuilder
                .UseTestServer()
                .ConfigureServices(services =>
                {
                    services.AddGrpc();
                    services.AddSingleton<ICartStore>(_ =>
                    {
                        var store = new ValkeyCartStore(NullLogger<ValkeyCartStore>.Instance, valkeyAddress);
                        store.Initialize();
                        return store;
                    });
                    services.AddSingleton(sp =>
                        new cart.services.CartService(
                            sp.GetRequiredService<ICartStore>(),
                            new ValkeyCartStore(NullLogger<ValkeyCartStore>.Instance, "badhost:1234"),
                            Api.Instance.GetClient()));
                })
                .Configure(app =>
                {
                    app.UseRouting();
                    app.UseEndpoints(endpoints => endpoints.MapGrpcService<cart.services.CartService>());
                });
        });
    }

    private async Task<(IHost server, CartServiceClient client)> StartAsync()
    {
        var server = await _host.StartAsync();
        var httpClient = server.GetTestClient();
        var channel = GrpcChannel.ForAddress(httpClient.BaseAddress, new GrpcChannelOptions
        {
            HttpClient = httpClient
        });
        return (server, new CartServiceClient(channel));
    }

    [Fact]
    public async Task GetItem_NoAddItemBefore_EmptyCartReturned()
    {
        var (server, client) = await StartAsync();
        using var _ = server;

        string userId = Guid.NewGuid().ToString();

        var cart = await client.GetCartAsync(new GetCartRequest { UserId = userId });
        Assert.NotNull(cart);

        // All grpc objects implement IEquitable, so we can compare equality with by-value semantics
        Assert.Equal(new Cart(), cart);
    }

    [Fact]
    public async Task AddItem_ItemExists_Updated()
    {
        var (server, client) = await StartAsync();
        using var _ = server;

        string userId = Guid.NewGuid().ToString();
        var request = new AddItemRequest
        {
            UserId = userId,
            Item = new CartItem
            {
                ProductId = "1",
                Quantity = 1
            }
        };

        // First add - nothing should fail
        await client.AddItemAsync(request);

        // Second add of existing product - quantity should be updated
        await client.AddItemAsync(request);

        var cart = await client.GetCartAsync(new GetCartRequest { UserId = userId });
        Assert.NotNull(cart);
        Assert.Equal(userId, cart.UserId);
        Assert.Single(cart.Items);
        Assert.Equal(2, cart.Items[0].Quantity);

        // Cleanup
        await client.EmptyCartAsync(new EmptyCartRequest { UserId = userId });
    }

    [Fact]
    public async Task AddItem_New_Inserted()
    {
        var (server, client) = await StartAsync();
        using var _ = server;

        string userId = Guid.NewGuid().ToString();
        var request = new AddItemRequest
        {
            UserId = userId,
            Item = new CartItem
            {
                ProductId = "1",
                Quantity = 1
            }
        };

        await client.AddItemAsync(request);

        var getCartRequest = new GetCartRequest { UserId = userId };
        var cart = await client.GetCartAsync(getCartRequest);
        Assert.NotNull(cart);
        Assert.Equal(userId, cart.UserId);
        Assert.Single(cart.Items);

        await client.EmptyCartAsync(new EmptyCartRequest { UserId = userId });
        cart = await client.GetCartAsync(getCartRequest);
        Assert.Empty(cart.Items);
    }

    [Fact]
    public async Task AddItem_ConcurrentCallsSameProduct_NoLostUpdates()
    {
        var (server, client) = await StartAsync();
        using var _ = server;

        string userId = Guid.NewGuid().ToString();
        const int concurrentCalls = 20;

        var tasks = Enumerable.Range(0, concurrentCalls).Select(_ => client.AddItemAsync(new AddItemRequest
        {
            UserId = userId,
            Item = new CartItem { ProductId = "race-product", Quantity = 1 }
        }).ResponseAsync);

        await Task.WhenAll(tasks);

        var cart = await client.GetCartAsync(new GetCartRequest { UserId = userId });
        Assert.Single(cart.Items);
        Assert.Equal(concurrentCalls, cart.Items[0].Quantity);

        await client.EmptyCartAsync(new EmptyCartRequest { UserId = userId });
    }

    [Fact]
    public async Task AddItem_NegativeDeltaDuringCheckoutRace_OnlyRemovesOrderedQuantity()
    {
        var (server, client) = await StartAsync();
        using var _ = server;

        string userId = Guid.NewGuid().ToString();

        // Simulates the state checkout observed via GetCart before placing the order.
        await client.AddItemAsync(new AddItemRequest
        {
            UserId = userId,
            Item = new CartItem { ProductId = "ordered-product", Quantity = 2 }
        });

        // A concurrent AddItem lands in the window between checkout's GetCart and its
        // post-order cart cleanup (e.g. a second browser tab, or a retried request).
        await client.AddItemAsync(new AddItemRequest
        {
            UserId = userId,
            Item = new CartItem { ProductId = "concurrently-added-product", Quantity = 1 }
        });

        // Checkout removes exactly what it read and ordered, not the whole cart.
        await client.AddItemAsync(new AddItemRequest
        {
            UserId = userId,
            Item = new CartItem { ProductId = "ordered-product", Quantity = -2 }
        });

        var cart = await client.GetCartAsync(new GetCartRequest { UserId = userId });
        var remaining = Assert.Single(cart.Items);
        Assert.Equal("concurrently-added-product", remaining.ProductId);
        Assert.Equal(1, remaining.Quantity);

        await client.EmptyCartAsync(new EmptyCartRequest { UserId = userId });
    }
}
