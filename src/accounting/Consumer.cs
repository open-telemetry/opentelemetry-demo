// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using Confluent.Kafka;
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


internal class Consumer : IDisposable
{
    private const string TopicName = "orders";
    private const string TraceParentHeaderName = "traceparent";
    private const string TraceStateHeaderName = "tracestate";

    private ILogger _logger;
    private IConsumer<string, byte[]> _consumer;
    private bool _isListening;
    private readonly string? _dbConnectionString;
    private static readonly ActivitySource MyActivitySource = new("Accounting.Consumer");

    public Consumer(ILogger<Consumer> logger)
    {
        _logger = logger;

        var servers = Environment.GetEnvironmentVariable("KAFKA_ADDR")
            ?? throw new InvalidOperationException("The KAFKA_ADDR environment variable is not set.");

        _consumer = BuildConsumer(servers);
        _consumer.Subscribe(TopicName);

       if (_logger.IsEnabled(LogLevel.Information))
       {
           _logger.LogInformation("Connecting to Kafka: {servers}", servers);
       }

        _dbConnectionString = Environment.GetEnvironmentVariable("DB_CONNECTION_STRING");
    }

    public void StartListening()
    {
        _isListening = true;

        try
        {
            while (_isListening)
            {
                try
                {
                    var consumeResult = _consumer.Consume();
                    using var activity = StartConsumerActivity(consumeResult);
                    ProcessMessage(consumeResult.Message);
                }
                catch (ConsumeException e)
                {
                    if (_logger.IsEnabled(LogLevel.Error))
                    {
                        _logger.LogError(e, "Consume error: {reason}", e.Error.Reason);
                    }
                }
            }
        }
        catch (OperationCanceledException)
        {
            _logger.LogInformation("Closing consumer");

            _consumer.Close();
        }
    }

    private static Activity? StartConsumerActivity(ConsumeResult<string, byte[]> consumeResult)
    {
        var activity = TryExtractParentContext(consumeResult.Message.Headers, out var parentContext)
            ? MyActivitySource.StartActivity("order-consumed", ActivityKind.Consumer, parentContext)
            : MyActivitySource.StartActivity("order-consumed", ActivityKind.Consumer);

        activity?.SetTag("messaging.system", "kafka");
        activity?.SetTag("messaging.destination.name", consumeResult.Topic);
        activity?.SetTag("messaging.operation", "process");
        activity?.SetTag("messaging.kafka.consumer.group", "accounting");
        activity?.SetTag("messaging.kafka.partition", consumeResult.Partition.Value);
        activity?.SetTag("messaging.kafka.message.offset", consumeResult.Offset.Value);

        return activity;
    }

    private static bool TryExtractParentContext(Headers headers, out ActivityContext parentContext)
    {
        parentContext = default;

        if (headers == null || !headers.TryGetLastBytes(TraceParentHeaderName, out var traceParentBytes))
        {
            return false;
        }

        var traceParent = Encoding.UTF8.GetString(traceParentBytes);
        var traceState = headers.TryGetLastBytes(TraceStateHeaderName, out var traceStateBytes)
            ? Encoding.UTF8.GetString(traceStateBytes)
            : null;

        return ActivityContext.TryParse(traceParent, traceState, out parentContext);
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
            _logger.LogInformation("Duplicate order received, skipping.");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Order parsing failed:");
        }
    }

    private static IConsumer<string, byte[]> BuildConsumer(string servers)
    {
        var conf = new ConsumerConfig
        {
            GroupId = $"accounting",
            BootstrapServers = servers,
            // https://github.com/confluentinc/confluent-kafka-dotnet/tree/07de95ed647af80a0db39ce6a8891a630423b952#basic-consumer-example
            AutoOffsetReset = AutoOffsetReset.Earliest,
            EnableAutoCommit = true
        };

        return new ConsumerBuilder<string, byte[]>(conf)
            .Build();
    }

    public void Dispose()
    {
        _isListening = false;
        _consumer?.Dispose();
    }
}
