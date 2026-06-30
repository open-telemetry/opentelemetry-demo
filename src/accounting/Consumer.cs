// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using Confluent.Kafka;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Npgsql;
using Oteldemo;
using Microsoft.EntityFrameworkCore;
using System.Diagnostics;
using System.Text;

namespace Accounting;

internal class DBContext : DbContext
{
    public DbSet<OrderEntity> Orders { get; set; }
    public DbSet<OrderItemEntity> CartItems { get; set; }
    public DbSet<ShippingEntity> Shipping { get; set; }

    protected override void OnConfiguring(DbContextOptionsBuilder optionsBuilder)
    {
        var connectionString = Environment.GetEnvironmentVariable("DB_CONNECTION_STRING");

        optionsBuilder.UseNpgsql(connectionString).UseSnakeCaseNamingConvention();
    }
}


internal class Consumer : BackgroundService
{
    private const string TopicName = "orders";

    private readonly ILogger _logger;
    private readonly IConsumer<string, byte[]> _consumer;
    private readonly string? _dbConnectionString;
    private static readonly ActivitySource MyActivitySource = new("Accounting.Consumer");

    public Consumer(ILogger<Consumer> logger)
    {
        _logger = logger;

        var servers = Environment.GetEnvironmentVariable("KAFKA_ADDR")
            ?? throw new InvalidOperationException("The KAFKA_ADDR environment variable is not set.");

        _consumer = BuildConsumer(servers);
        _consumer.Subscribe(TopicName);

        Log.KafkaConnecting(_logger, servers);

        _dbConnectionString = Environment.GetEnvironmentVariable("DB_CONNECTION_STRING");
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        await Task.Yield();

        try
        {
            while (!stoppingToken.IsCancellationRequested)
            {
                try
                {
                    var consumeResult = _consumer.Consume(stoppingToken);
                    using var activity = StartOrderConsumedActivity(consumeResult.Message.Headers);
                    ProcessMessage(consumeResult.Message);
                }
                catch (ConsumeException e)
                {
                    Log.ConsumeError(_logger, e, e.Error.Reason);
                }
            }
        }
        catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
        {
        }
        finally
        {
            Log.ConsumerClosing(_logger);
            _consumer.Close();
        }
    }

    private void ProcessMessage(Message<string, byte[]> message)
    {
        try
        {
            var order = OrderResult.Parser.ParseFrom(message.Value);
            Log.OrderReceivedMessage(_logger, order);

            if (_dbConnectionString == null)
            {
                return;
            }

            using var dbContext = new DBContext();
            var orderEntity = new OrderEntity
            {
                Id = order.OrderId
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
        }
        catch (DbUpdateException ex) when (ex.InnerException is PostgresException { SqlState: PostgresErrorCodes.UniqueViolation })
        {
            Log.DuplicateOrderSkipped(_logger);
        }
        catch (Exception ex)
        {
            Log.OrderParsingFailed(_logger, ex);
        }
    }

    private static Activity? StartOrderConsumedActivity(Headers headers)
    {
        var traceParent = GetHeaderValue(headers, "traceparent");

        if (traceParent != null && ActivityContext.TryParse(
            traceParent,
            GetHeaderValue(headers, "tracestate"),
            isRemote: true,
            out var parentContext))
        {
            return MyActivitySource.StartActivity("order-consumed", ActivityKind.Consumer, parentContext);
        }

        return MyActivitySource.StartActivity("order-consumed", ActivityKind.Consumer);
    }

    private static string? GetHeaderValue(Headers headers, string key)
    {
        var header = headers.LastOrDefault(header => string.Equals(header.Key, key, StringComparison.OrdinalIgnoreCase));
        var value = header?.GetValueBytes();

        return value == null ? null : Encoding.UTF8.GetString(value);
    }

    private static IConsumer<string, byte[]> BuildConsumer(string servers)
    {
        var conf = new ConsumerConfig
        {
            GroupId = "accounting",
            BootstrapServers = servers,
            // https://github.com/confluentinc/confluent-kafka-dotnet/tree/07de95ed647af80a0db39ce6a8891a630423b952#basic-consumer-example
            AutoOffsetReset = AutoOffsetReset.Earliest,
            EnableAutoCommit = true
        };

        return new ConsumerBuilder<string, byte[]>(conf)
            .Build();
    }

    public override void Dispose()
    {
        _consumer?.Dispose();
        base.Dispose();
    }
}
