// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using MongoDB.Bson;
using MongoDB.Bson.Serialization.Attributes;

namespace Accounting;

// Represents a single document in the 'orders' collection in MongoDB.
public class OrderDocument
{
    // The unique ID for the MongoDB document.
    [BsonId]
    [BsonRepresentation(BsonType.ObjectId)]
    public string? Id { get; set; }

    public required string OrderId { get; set; }
    public required ShippingDocument Shipping { get; set; }
    public required List<OrderItemDocument> Items { get; set; }
}

public class ShippingDocument
{
    public required string ShippingTrackingId { get; set; }
    public required string ShippingCostCurrencyCode { get; set; }
    public required long ShippingCostUnits { get; set; }
    public required int ShippingCostNanos { get; set; }
    public required string StreetAddress { get; set; }
    public required string City { get; set; }
    public required string State { get; set; }
    public required string Country { get; set; }
    public required string ZipCode { get; set; }
}

public class OrderItemDocument
{
    public required string ItemCostCurrencyCode { get; set; }
    public required long ItemCostUnits { get; set; }
    public required int ItemCostNanos { get; set; }
    public required string ProductId { get; set; }
    public required int Quantity { get; set; }
}