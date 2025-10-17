// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using MongoDB.Driver;
using MongoDB.Driver.Core.Extensions.DiagnosticSources;
using Oteldemo;
using System;
using System.Linq;
using System.Threading.Tasks;

namespace Accounting
{
    public class MongoDataService
    {
        private readonly IMongoCollection<OrderDocument> _ordersCollection;

        public MongoDataService()
        {
            var connectionString = Environment.GetEnvironmentVariable("DB_CONNECTION_STRING")
                ?? throw new ArgumentNullException("DB_CONNECTION_STRING for MongoDB is not set.");

            var mongoUrl = new MongoUrl(connectionString);
            var clientSettings = MongoClientSettings.FromUrl(mongoUrl);
            clientSettings.ClusterConfigurator = cb => cb.Subscribe(new DiagnosticsActivityEventSubscriber());
            var mongoClient = new MongoClient(clientSettings);

            // Use database from connection string if available, fallback to 'accounting_db'
            var dbName = !string.IsNullOrWhiteSpace(mongoUrl.DatabaseName) ? mongoUrl.DatabaseName : "accounting_db";
            var mongoDatabase = mongoClient.GetDatabase(dbName);

            _ordersCollection = mongoDatabase.GetCollection<OrderDocument>("orders");
        }

        public async Task SaveOrderAsync(OrderResult order)
        {
            var orderDocument = new OrderDocument
            {
                OrderId = order.OrderId,
                Shipping = new ShippingDocument
                {
                    ShippingTrackingId = order.ShippingTrackingId,
                    ShippingCostCurrencyCode = order.ShippingCost.CurrencyCode,
                    ShippingCostUnits = order.ShippingCost.Units,
                    ShippingCostNanos = order.ShippingCost.Nanos,
                    StreetAddress = order.ShippingAddress.StreetAddress,
                    City = order.ShippingAddress.City,
                    State = order.ShippingAddress.State,
                    Country = order.ShippingAddress.Country,
                    ZipCode = order.ShippingAddress.ZipCode
                },
                Items = order.Items.Select(item => new OrderItemDocument
                {
                    ProductId = item.Item.ProductId,
                    Quantity = item.Item.Quantity,
                    ItemCostCurrencyCode = item.Cost.CurrencyCode,
                    ItemCostUnits = item.Cost.Units,
                    ItemCostNanos = item.Cost.Nanos
                }).ToList()
            };

            try
            {
                Console.WriteLine($"[MongoDataService] Attempting insert for OrderId={orderDocument.OrderId}");
                await _ordersCollection.InsertOneAsync(orderDocument);
                Console.WriteLine($"[MongoDataService] Insert succeeded for OrderId={orderDocument.OrderId}");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[MongoDataService] Insert FAILED for OrderId={orderDocument.OrderId}: {ex}");
                throw;
            }
        }
    }
}