// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
using System.Diagnostics;
using System.Threading.Tasks;
using Grpc.Core;
using cartservice.cartstore;
using Oteldemo;

namespace cartservice.services
{
    public class CartService : Oteldemo.CartService.CartServiceBase
    {
        private readonly static Empty Empty = new Empty();
        private readonly ICartStore _cartStore;

        public CartService(ICartStore cartStore)
        {
            _cartStore = cartStore;
        }

        public async override Task<Empty> AddItem(AddItemRequest request, ServerCallContext context)
        {
            var activity = Activity.Current;
            activity?.SetTag("app.user.id", request.UserId);
            activity?.SetTag("app.product.id", request.Item.ProductId);
            activity?.SetTag("app.product.quantity", request.Item.Quantity);

            await _cartStore.AddItemAsync(request.UserId, request.Item.ProductId, request.Item.Quantity);
            return Empty;
        }

        public async override Task<Cart> GetCart(GetCartRequest request, ServerCallContext context)
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

        public async override Task<Empty> EmptyCart(EmptyCartRequest request, ServerCallContext context)
        {
            var activity = Activity.Current;
            activity?.SetTag("app.user.id", request.UserId);
            activity?.AddEvent(new("Empty cart"));

            await _cartStore.EmptyCartAsync(request.UserId);
            return Empty;
        }
    }
}
