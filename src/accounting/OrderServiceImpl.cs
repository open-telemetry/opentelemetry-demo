// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using Grpc.Core;
using Microsoft.EntityFrameworkCore;
using Oteldemo;

namespace Accounting;

internal class OrderServiceImpl : OrderService.OrderServiceBase
{
    private readonly IDbContextFactory<AccountingDbContext> _dbContextFactory;

    public OrderServiceImpl(IDbContextFactory<AccountingDbContext> dbContextFactory)
    {
        _dbContextFactory = dbContextFactory;
    }

    public override async Task<GetOrdersByEmailResponse> GetOrdersByEmail(GetOrdersByEmailRequest request, ServerCallContext context)
    {
        using var db = _dbContextFactory.CreateDbContext();

        var orders = await db.Orders
            .Where(o => o.Email == request.Email)
            .OrderByDescending(o => o.CreatedAt)
            .ToListAsync(context.CancellationToken);

        var response = new GetOrdersByEmailResponse();

        foreach (var order in orders)
        {
            var items = await db.CartItems
                .Where(i => i.OrderId == order.Id)
                .ToListAsync(context.CancellationToken);

            var shipping = await db.Shipping
                .Where(s => s.OrderId == order.Id)
                .FirstOrDefaultAsync(context.CancellationToken);

            response.Orders.Add(MapToOrderDetail(order, items, shipping));
        }

        return response;
    }

    public override async Task<OrderDetail> GetOrder(GetOrderRequest request, ServerCallContext context)
    {
        using var db = _dbContextFactory.CreateDbContext();

        var order = await db.Orders
            .FirstOrDefaultAsync(o => o.Id == request.OrderId, context.CancellationToken);

        if (order == null)
        {
            throw new RpcException(new Status(StatusCode.NotFound, $"Order {request.OrderId} not found"));
        }

        var items = await db.CartItems
            .Where(i => i.OrderId == order.Id)
            .ToListAsync(context.CancellationToken);

        var shipping = await db.Shipping
            .Where(s => s.OrderId == order.Id)
            .FirstOrDefaultAsync(context.CancellationToken);

        return MapToOrderDetail(order, items, shipping);
    }

    private static OrderDetail MapToOrderDetail(OrderEntity order, List<OrderItemEntity> items, ShippingEntity? shipping)
    {
        var detail = new OrderDetail
        {
            OrderId = order.Id,
            Email = order.Email ?? "",
            Status = order.OrderStatus,
            CreatedAt = order.CreatedAt.ToString("O"),
            TransactionId = order.TransactionId ?? "",
            RefundTransactionId = order.RefundTransactionId ?? "",
        };

        if (order.TotalCostCurrencyCode != null)
        {
            detail.TotalCost = new Money
            {
                CurrencyCode = order.TotalCostCurrencyCode,
                Units = order.TotalCostUnits ?? 0,
                Nanos = order.TotalCostNanos ?? 0,
            };
        }

        if (shipping != null)
        {
            detail.ShippingTrackingId = shipping.ShippingTrackingId;
            detail.ShippingAddress = new Address
            {
                StreetAddress = shipping.StreetAddress,
                City = shipping.City,
                State = shipping.State,
                Country = shipping.Country,
                ZipCode = shipping.ZipCode,
            };
        }

        foreach (var item in items)
        {
            detail.Items.Add(new OrderItem
            {
                Item = new CartItem
                {
                    ProductId = item.ProductId,
                    Quantity = item.Quantity,
                },
                Cost = new Money
                {
                    CurrencyCode = item.ItemCostCurrencyCode,
                    Units = item.ItemCostUnits,
                    Nanos = item.ItemCostNanos,
                },
            });
        }

        return detail;
    }
}
