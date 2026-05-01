// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using Microsoft.EntityFrameworkCore;
using System.ComponentModel.DataAnnotations.Schema;

namespace Accounting;

[Table("shipping", Schema = "accounting")]
[PrimaryKey(nameof(ShippingTrackingId))]
internal class ShippingEntity
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

    public required string OrderId { get; set; }
}

[Table("orderitem", Schema = "accounting")]
[PrimaryKey(nameof(ProductId), nameof(OrderId))]
internal class OrderItemEntity
{
    public required string ItemCostCurrencyCode { get; set; }

    public required long ItemCostUnits { get; set; }

    public required int ItemCostNanos { get; set; }

    public required string ProductId { get; set; }

    public required int Quantity { get; set; }

    public required string OrderId { get; set; }
}

[Table("order", Schema = "accounting")]
[PrimaryKey(nameof(Id))]
internal class OrderEntity
{
    [Column("order_id")]
    public required string Id { get; set; }

    [Column("email")]
    public string? Email { get; set; }

    [Column("user_id")]
    public string? UserId { get; set; }

    [Column("transaction_id")]
    public string? TransactionId { get; set; }

    [Column("total_cost_currency_code")]
    public string? TotalCostCurrencyCode { get; set; }

    [Column("total_cost_units")]
    public long? TotalCostUnits { get; set; }

    [Column("total_cost_nanos")]
    public int? TotalCostNanos { get; set; }

    [Column("order_status")]
    public string OrderStatus { get; set; } = "completed";

    [Column("created_at")]
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

    [Column("refunded_at")]
    public DateTime? RefundedAt { get; set; }

    [Column("refund_transaction_id")]
    public string? RefundTransactionId { get; set; }

}
