// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using Confluent.Kafka;
using Google.Protobuf;
using Microsoft.Extensions.Logging;
using Npgsql;
using Oteldemo;
using Microsoft.EntityFrameworkCore;
using System.Diagnostics;

namespace Accounting;

internal class AccountingDbContext : DbContext
{
    public DbSet<OrderEntity> Orders { get; set; }
    public DbSet<OrderItemEntity> CartItems { get; set; }
    public DbSet<ShippingEntity> Shipping { get; set; }

    public AccountingDbContext(DbContextOptions<AccountingDbContext> options) : base(options)
    {
    }
}


internal class Consumer : BackgroundService
{
    private const string OrdersTopic = "orders";
    private const string RefundsTopic = "refunds";

    private readonly ILogger _logger;
    private readonly IConsumer<string, byte[]> _consumer;
    private readonly IDbContextFactory<AccountingDbContext>? _dbContextFactory;
    private static readonly ActivitySource MyActivitySource = new("Accounting.Consumer");

    public Consumer(ILogger<Consumer> logger, IDbContextFactory<AccountingDbContext>? dbContextFactory = null)
    {
        _logger = logger;
        _dbContextFactory = dbContextFactory;

        var servers = Environment.GetEnvironmentVariable("KAFKA_ADDR")
            ?? throw new ArgumentNullException("KAFKA_ADDR");

        _consumer = BuildConsumer(servers);
        _consumer.Subscribe(new[] { OrdersTopic, RefundsTopic });

        _logger.LogInformation($"Connecting to Kafka: {servers}");
    }

    protected override Task ExecuteAsync(CancellationToken stoppingToken)
    {
        return Task.Run(() =>
        {
            try
            {
                while (!stoppingToken.IsCancellationRequested)
                {
                    try
                    {
                        var consumeResult = _consumer.Consume(stoppingToken);
                        var topic = consumeResult.Topic;
                        using var activity = MyActivitySource.StartActivity(
                            topic == RefundsTopic ? "refund-consumed" : "order-consumed",
                            ActivityKind.Internal);

                        var result = topic switch
                        {
                            OrdersTopic => ProcessOrder(consumeResult.Message),
                            RefundsTopic => ProcessRefund(consumeResult.Message),
                            _ => ProcessResult.Processed,
                        };

                        if (result == ProcessResult.Processed)
                        {
                            _consumer.Commit(consumeResult);
                        }
                        else
                        {
                            // Rewind so the next Consume() re-delivers the same offset.
                            _consumer.Seek(consumeResult.TopicPartitionOffset);
                            Thread.Sleep(TimeSpan.FromSeconds(1));
                        }
                    }
                    catch (ConsumeException e)
                    {
                        _logger.LogError(e, "Consume error: {0}", e.Error.Reason);
                    }
                }
            }
            catch (OperationCanceledException)
            {
                _logger.LogInformation("Closing consumer");
            }
            finally
            {
                _consumer.Close();
            }
        }, stoppingToken);
    }

    private enum ProcessResult
    {
        Processed,
        Retry,
    }

    private ProcessResult ProcessOrder(Message<string, byte[]> message)
    {
        OrderResult order;
        try
        {
            order = OrderResult.Parser.ParseFrom(message.Value);
        }
        catch (InvalidProtocolBufferException ex)
        {
            // Poison pill — unparseable payload will never succeed on retry.
            _logger.LogError(ex, "Dropping unparseable Kafka message");
            return ProcessResult.Processed;
        }

        Log.OrderReceivedMessage(_logger, order);

        if (_dbContextFactory == null)
        {
            return ProcessResult.Processed;
        }

        try
        {
            using var dbContext = _dbContextFactory.CreateDbContext();

            // At-least-once delivery from Kafka + offset commits after DB write
            // means restart windows can replay already-persisted messages.
            // Skip the insert if this order_id is already in the DB.
            if (dbContext.Orders.Any(o => o.Id == order.OrderId))
            {
                return ProcessResult.Processed;
            }

            var orderEntity = new OrderEntity
            {
                Id = order.OrderId,
                Email = string.IsNullOrEmpty(order.Email) ? null : order.Email,
                UserId = string.IsNullOrEmpty(order.UserId) ? null : order.UserId,
                TransactionId = string.IsNullOrEmpty(order.TransactionId) ? null : order.TransactionId,
                TotalCostCurrencyCode = order.TotalCost?.CurrencyCode,
                TotalCostUnits = order.TotalCost?.Units,
                TotalCostNanos = order.TotalCost?.Nanos,
            };
            dbContext.Add(orderEntity);
            foreach (var item in order.Items)
            {
                var orderItem = new OrderItemEntity
                {
                    ItemCostCurrencyCode = item.Cost.CurrencyCode,
                    ItemCostUnits = item.Cost.Units,
                    ItemCostNanos = item.Cost.Nanos,
                    ProductId = item.Item.ProductId,
                    Quantity = item.Item.Quantity,
                    OrderId = order.OrderId
                };

                dbContext.Add(orderItem);
            }

            var shipping = new ShippingEntity
            {
                ShippingTrackingId = order.ShippingTrackingId,
                ShippingCostCurrencyCode = order.ShippingCost.CurrencyCode,
                ShippingCostUnits = order.ShippingCost.Units,
                ShippingCostNanos = order.ShippingCost.Nanos,
                StreetAddress = order.ShippingAddress.StreetAddress,
                City = order.ShippingAddress.City,
                State = order.ShippingAddress.State,
                Country = order.ShippingAddress.Country,
                ZipCode = order.ShippingAddress.ZipCode,
                OrderId = order.OrderId
            };
            dbContext.Add(shipping);
            dbContext.SaveChanges();
            return ProcessResult.Processed;
        }
        catch (DbUpdateException ex) when (ex.InnerException is PostgresException { SqlState: "23505" })
        {
            // Racy idempotent check — row appeared between Any() and SaveChanges().
            // Data is persisted; safe to commit.
            _logger.LogWarning(ex, "Duplicate order {OrderId}; treating as processed", order.OrderId);
            return ProcessResult.Processed;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to persist order {OrderId}; rewinding for retry", order.OrderId);
            return ProcessResult.Retry;
        }
    }

    private ProcessResult ProcessRefund(Message<string, byte[]> message)
    {
        RefundResult refund;
        try
        {
            refund = RefundResult.Parser.ParseFrom(message.Value);
        }
        catch (InvalidProtocolBufferException ex)
        {
            _logger.LogError(ex, "Dropping unparseable refund message");
            return ProcessResult.Processed;
        }

        if (_dbContextFactory == null)
        {
            return ProcessResult.Processed;
        }

        try
        {
            using var dbContext = _dbContextFactory.CreateDbContext();
            var order = dbContext.Orders.FirstOrDefault(o => o.Id == refund.OrderId);
            if (order == null)
            {
                // Either the order hasn't been consumed yet, or it expired.
                // The refund event commits anyway — replaying it later won't help.
                _logger.LogWarning("Refund for unknown order {OrderId}; dropping", refund.OrderId);
                return ProcessResult.Processed;
            }

            if (order.OrderStatus == "refunded")
            {
                // Idempotent — already applied.
                return ProcessResult.Processed;
            }

            order.OrderStatus = "refunded";
            order.RefundedAt = DateTime.UtcNow;
            order.RefundTransactionId = string.IsNullOrEmpty(refund.RefundTransactionId)
                ? null
                : refund.RefundTransactionId;
            dbContext.SaveChanges();

            _logger.LogInformation("Marked order {OrderId} refunded (txn {RefundTxn})",
                refund.OrderId, refund.RefundTransactionId);
            return ProcessResult.Processed;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to apply refund for {OrderId}; rewinding for retry", refund.OrderId);
            return ProcessResult.Retry;
        }
    }

    private IConsumer<string, byte[]> BuildConsumer(string servers)
    {
        var conf = new ConsumerConfig
        {
            GroupId = $"accounting",
            BootstrapServers = servers,
            // https://github.com/confluentinc/confluent-kafka-dotnet/tree/07de95ed647af80a0db39ce6a8891a630423b952#basic-consumer-example
            AutoOffsetReset = AutoOffsetReset.Earliest,
            EnableAutoCommit = false,
            QueuedMaxMessagesKbytes = 4096,
            MaxPartitionFetchBytes = 262144,
        };

        return new ConsumerBuilder<string, byte[]>(conf)
            .Build();
    }
}
