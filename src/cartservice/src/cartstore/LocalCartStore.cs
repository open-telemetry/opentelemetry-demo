// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
using System;
using System.Collections.Concurrent;
using System.Diagnostics;
using System.Linq;
using System.Threading.Tasks;

namespace cartservice.cartstore
{
    internal class LocalCartStore : ICartStore
    {
        // Maps between user and their cart
        private ConcurrentDictionary<string, Oteldemo.Cart> userCartItems = new ConcurrentDictionary<string, Oteldemo.Cart>();
        private readonly Oteldemo.Cart emptyCart = new Oteldemo.Cart();

        public Task InitializeAsync()
        {
            Console.WriteLine("Local Cart Store was initialized");

            return Task.CompletedTask;
        }

        public Task AddItemAsync(string userId, string productId, int quantity)
        {
            Console.WriteLine($"AddItemAsync called with userId={userId}, productId={productId}, quantity={quantity}");
            var newCart = new Oteldemo.Cart
                {
                    UserId = userId,
                    Items = { new Oteldemo.CartItem { ProductId = productId, Quantity = quantity } }
                };
            userCartItems.AddOrUpdate(userId, newCart,
            (k, exVal) =>
            {
                // If the item exists, we update its quantity
                var existingItem = exVal.Items.SingleOrDefault(item => item.ProductId == productId);
                if (existingItem != null)
                {
                    existingItem.Quantity += quantity;
                }
                else
                {
                    exVal.Items.Add(new Oteldemo.CartItem { ProductId = productId, Quantity = quantity });
                }

                return exVal;
            });

            return Task.CompletedTask;
        }

        public Task EmptyCartAsync(string userId)
        {
            var eventTags = new ActivityTagsCollection();
            eventTags.Add("userId", userId);
            Activity.Current?.AddEvent(new ActivityEvent("EmptyCartAsync called.", default, eventTags));

            userCartItems[userId] = new Oteldemo.Cart();
            return Task.CompletedTask;
        }

        public Task<Oteldemo.Cart> GetCartAsync(string userId)
        {
            Console.WriteLine($"GetCartAsync called with userId={userId}");
            Oteldemo.Cart cart = null;
            if (!userCartItems.TryGetValue(userId, out cart))
            {
                Console.WriteLine($"No carts for user {userId}");
                return Task.FromResult(emptyCart);
            }

            return Task.FromResult(cart);
        }

        public bool Ping()
        {
            return true;
        }
    }
}
