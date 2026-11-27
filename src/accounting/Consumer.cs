// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using Confluent.Kafka;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Npgsql;
using Oteldemo;
using Microsoft.EntityFrameworkCore;
using System.Diagnostics;

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


public class Consumer : BackgroundService
{
    private static readonly string TopicName = Environment.GetEnvironmentVariable("KAFKA_TOPIC") ?? "orders";

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
                    using var activity = MyActivitySource.StartActivity("order-consumed",  ActivityKind.Internal);
                    var consumeResult = _consumer.Consume(stoppingToken);
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

    public static IConsumer<string, byte[]> BuildConsumer(string servers)
    {
        var conf = new ConsumerConfig
        {
            GroupId = "accounting",
            BootstrapServers = servers,
            // https://github.com/confluentinc/confluent-kafka-dotnet/tree/07de95ed647af80a0db39ce6a8891a630423b952#basic-consumer-example
            AutoOffsetReset = AutoOffsetReset.Earliest,
            EnableAutoCommit = true
        };

        // Optional TLS/SASL settings for Kafka clusters that require them. Without them the connection stays plaintext.
        var securityProtocol = Environment.GetEnvironmentVariable("KAFKA_SECURITY_PROTOCOL");
        if (!string.IsNullOrEmpty(securityProtocol))
        {
            // Validate security protocol
            var upperProtocol = securityProtocol.ToUpperInvariant();
            if (upperProtocol != "PLAINTEXT" && upperProtocol != "SSL" && upperProtocol != "SASL_PLAINTEXT" && upperProtocol != "SASL_SSL")
            {
                throw new InvalidOperationException(
                    $"Unsupported KAFKA_SECURITY_PROTOCOL: {securityProtocol}. " +
                    "Supported values: PLAINTEXT, SSL, SASL_PLAINTEXT, SASL_SSL"
                );
            }

            conf.Set("security.protocol", securityProtocol.ToUpperInvariant());

            if (securityProtocol.StartsWith("SASL_", StringComparison.OrdinalIgnoreCase))
            {
                var mechanism = Environment.GetEnvironmentVariable("KAFKA_SASL_MECHANISM") is { Length: > 0 } m ? m : "PLAIN";

                // Validate SASL mechanism
                var upperMechanism = mechanism.ToUpperInvariant();
                if (upperMechanism != "PLAIN" && upperMechanism != "SCRAM-SHA-256" && upperMechanism != "SCRAM-SHA-512")
                {
                    throw new InvalidOperationException(
                        $"Unsupported KAFKA_SASL_MECHANISM: {mechanism}. " +
                        "Supported values: PLAIN, SCRAM-SHA-256, SCRAM-SHA-512"
                    );
                }

                conf.Set("sasl.mechanism", mechanism.ToUpperInvariant());
                conf.SaslUsername = Environment.GetEnvironmentVariable("KAFKA_SASL_USERNAME");
                conf.SaslPassword = Environment.GetEnvironmentVariable("KAFKA_SASL_PASSWORD");

                // Ensure credentials are provided when SASL is enabled
                if (string.IsNullOrEmpty(conf.SaslUsername))
                {
                    throw new InvalidOperationException("KAFKA_SASL_USERNAME is required when SASL is enabled");
                }
                if (string.IsNullOrEmpty(conf.SaslPassword))
                {
                    throw new InvalidOperationException("KAFKA_SASL_PASSWORD is required when SASL is enabled");
                }
            }
        }

        return new ConsumerBuilder<string, byte[]>(conf)
            .Build();
    }

    public override void Dispose()
    {
        _consumer?.Dispose();
        base.Dispose();
    }
}
