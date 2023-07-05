// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
using System.Diagnostics;
using System.Threading.Tasks;
using Grpc.Core;
using OpenTelemetry.Trace;
using cartservice.cartstore;
using cartservice.featureflags;
using Oteldemo;

namespace cartservice.services;

public class CartService : Oteldemo.CartService.CartServiceBase
{
    private static readonly Empty Empty = new();
    private static readonly ICartStore BadCartStore = new RedisCartStore("badhost:1234");
    private readonly ICartStore _cartStore;
    private readonly FeatureFlagHelper _featureFlagHelper;

    public CartService(ICartStore cartStore, FeatureFlagHelper featureFlagService)
    {
        _cartStore = cartStore;
        _featureFlagHelper = featureFlagService;
    }

    public override async Task<Empty> AddItem(AddItemRequest request, ServerCallContext context)
    {
        var activity = Activity.Current;
        activity?.SetTag("app.user.id", request.UserId);
        activity?.SetTag("app.product.id", request.Item.ProductId);
        activity?.SetTag("app.product.quantity", request.Item.Quantity);

        await _cartStore.AddItemAsync(request.UserId, request.Item.ProductId, request.Item.Quantity);
        return Empty;
    }

    public override async Task<Cart> GetCart(GetCartRequest request, ServerCallContext context)
    {
        var activity = Activity.Current;
        activity?.SetTag("app.user.id", request.UserId);
        activity?.AddEvent(new("Fetch cart"));

        var cart = await _cartStore.GetCartAsync(request.UserId);
        var totalCart = 0;
        foreach (var item in cart.Items)
        {
            totalCart += item.Quantity;
        }
        activity?.SetTag("app.cart.items.count", totalCart);

        return cart;
    }

    public override async Task<Empty> EmptyCart(EmptyCartRequest request, ServerCallContext context)
    {
        var activity = Activity.Current;
        activity?.SetTag("app.user.id", request.UserId);
        activity?.AddEvent(new("Empty cart"));

        try
        {
            if (await _featureFlagHelper.GenerateCartError())
            {
                await BadCartStore.EmptyCartAsync(request.UserId);
            }
            else
            {
                await _cartStore.EmptyCartAsync(request.UserId);
            }
        }
        catch (RpcException ex)
        {
            Activity.Current?.RecordException(ex);
            Activity.Current?.SetStatus(ActivityStatusCode.Error, ex.Message);
            throw;
        }

        return Empty;
    }
}
