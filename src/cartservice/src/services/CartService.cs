// Copyright 2020 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

using System;
using System.Diagnostics;
using System.Threading.Tasks;
using Grpc.Core;
using OpenTelemetry.Trace;
using cartservice.cartstore;
using Hipstershop;

namespace cartservice.services
{
    public class CartService : Hipstershop.CartService.CartServiceBase
    {
        private readonly static Empty Empty = new Empty();
        private readonly static Random _random = new Random();
        private ICartStore _cartStore;

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
            this._cartStore = _random.Next() % 5 != 0 
                ? this._cartStore
                : new RedisCartStore("badhost:4567");

            var activity = Activity.Current;
            activity?.SetTag("app.user.id", request.UserId);
            activity?.AddEvent(new("Empty cart"));

            try
            {
                await _cartStore.EmptyCartAsync(request.UserId);
            }
            catch (Exception e)
            {
                // Recording the original exception to preserve the stack trace on the activity event
                activity?.RecordException(e);

                // Throw a new exception and use its message for the status description
                var ex = new Exception("Can't access cart storage.");
                Activity.Current?.SetStatus(ActivityStatusCode.Error, ex.Message);
                throw ex;
            }

            return Empty;
        }
    }
}
