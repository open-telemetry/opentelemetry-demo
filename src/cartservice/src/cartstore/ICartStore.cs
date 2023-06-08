// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
using System.Threading.Tasks;

namespace cartservice.cartstore
{
    public interface ICartStore
    {
        Task InitializeAsync();

        Task AddItemAsync(string userId, string productId, int quantity);
        Task EmptyCartAsync(string userId);

        Task<Oteldemo.Cart> GetCartAsync(string userId);

        bool Ping();
    }
}
