// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using Confluent.Kafka;
using Microsoft.Extensions.Logging;
using Microsoft.EntityFrameworkCore;
using System.Diagnostics;
using OpenTelemetry;
using OpenTelemetry.Context.Propagation;
using System.Data;
using Microsoft.Data.SqlClient;
using System.Text;
using System.Text.Json;
using Oteldemo; // <- add this so OrderResult resolves

// NOTE: adjust namespaces to your project layout
namespace Accounting;

/// <summary>
/// Entities for SQL Server
/// </summary>

/// <summary>
/// Raw message table (one row per consumed Kafka message)
/// </summary>
internal class RawKafkaMessageEntity
{
    public long Id { get; set; }                 // IDENTITY
    public string? Key { get; set; }             // Kafka key (nullable)
    public byte[] Value { get; set; } = default!;// Kafka value (raw bytes)
    public string? HeadersJson { get; set; }     // Kafka headers (serialized as JSON)
    public DateTime ReceivedAtUtc { get; set; }  // Timestamp (UTC)
}

/// <summary>
/// Output table for "messages written today"
/// </summary>
internal class TodayMessageEntity
{
    public long Id { get; set; }                 // IDENTITY
    public long MessageId { get; set; }          // FK to RawKafkaMessages.Id
    public string? Key { get; set; }
    public DateTime ReceivedAtUtc { get; set; }
}

internal class DBContext : DbContext
{
    public DbSet<OrderEntity> Orders { get; set; } = default!;
    public DbSet<OrderItemEntity> CartItems { get; set; } = default!;
    public DbSet<ShippingEntity> Shipping { get; set; } = default!;

    public DbSet<RawKafkaMessageEntity> RawKafkaMessages { get; set; } = default!;
    public DbSet<TodayMessageEntity> TodayMessages { get; set; } = default!;

    protected override void OnConfiguring(DbContextOptionsBuilder optionsBuilder)
    {
        // Use a SQL Server connection string:
        // e.g. "Server=tcp:host,1433;Database=MyDb;User Id=sa;Password=...;Encrypt=True;TrustServerCertificate=True"
        var connectionString = Environment.GetEnvironmentVariable("DB_CONNECTION_STRING");
        optionsBuilder.UseSqlServer(connectionString);
    }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<OrderEntity>(b =>
        {
            b.ToTable("orders");
            b.HasKey(x => x.Id);
        });

        modelBuilder.Entity<OrderItemEntity>(b =>
        {
            b.ToTable("orderitem"); // match attribute (or drop this line & let attribute win)
            b.HasKey(x => new { x.ProductId, x.OrderId }); // ✅ correct composite key
            b.Property(x => x.ProductId).IsRequired();
            b.Property(x => x.OrderId).IsRequired();
        });

        modelBuilder.Entity<ShippingEntity>(b =>
        {
            b.ToTable("shipping"); // matches attribute
            b.HasKey(x => x.ShippingTrackingId);
        });

        modelBuilder.Entity<RawKafkaMessageEntity>(b =>
        {
            b.ToTable("RawKafkaMessages");
            b.HasKey(x => x.Id);
            b.Property(x => x.Id).UseIdentityColumn();
            b.Property(x => x.Value).HasColumnType("varbinary(max)").IsRequired();
            b.Property(x => x.HeadersJson).HasColumnType("nvarchar(max)");
            b.Property(x => x.ReceivedAtUtc).HasColumnType("datetime2").IsRequired();
            b.Property(x => x.Key).HasMaxLength(1024);
            b.HasIndex(x => x.ReceivedAtUtc);
        });

        modelBuilder.Entity<TodayMessageEntity>(b =>
        {
            b.ToTable("TodayMessages");
            b.HasKey(x => x.Id);
            b.Property(x => x.Id).UseIdentityColumn();
            b.Property(x => x.ReceivedAtUtc).HasColumnType("datetime2").IsRequired();
            b.HasIndex(x => x.MessageId).IsUnique(); // keep 1-1 with raw row
        });
    }
}

/// <summary>
/// Minimal, extensible SQL task runner. Add more tasks to the list to grow the pipeline.
/// </summary>
internal interface ISqlPostProcessor
{
    void Run(SqlConnection conn, SqlTransaction? tx = null);
}

internal class TodayMessagesSqlTask : ISqlPostProcessor
{
    public void Run(SqlConnection conn, SqlTransaction? tx = null)
    {
        // Insert "today's" messages (UTC) into TodayMessages, idempotently.
        // Using CAST(date) to ignore time component.
        var cmd = conn.CreateCommand();
        cmd.Transaction = tx;
        cmd.CommandText = @"
INSERT INTO TodayMessages (MessageId, [Key], ReceivedAtUtc)
SELECT m.Id, m.[Key], m.ReceivedAtUtc
FROM RawKafkaMessages m
LEFT JOIN TodayMessages t ON t.MessageId = m.Id
WHERE t.MessageId IS NULL
  AND CAST(m.ReceivedAtUtc AS date) = CAST(SYSUTCDATETIME() AS date);
";
        cmd.CommandType = CommandType.Text;
        cmd.ExecuteNonQuery();
    }
}

internal class SqlPostInsertPipeline
{
    private readonly List<ISqlPostProcessor> _tasks = new();

    public SqlPostInsertPipeline Add(ISqlPostProcessor task)
    {
        _tasks.Add(task);
        return this;
    }

    public void RunAll(SqlConnection conn, SqlTransaction? tx = null)
    {
        foreach (var t in _tasks)
        {
            t.Run(conn, tx);
        }
    }
}

internal static class KafkaHeaderSerializer
{
    public static string ToJson(Headers headers)
    {
        var dict = new Dictionary<string, List<string>>();
        foreach (var h in headers)
        {
            if (!dict.TryGetValue(h.Key, out var list))
            {
                list = new List<string>();
                dict[h.Key] = list;
            }
            list.Add(h.GetValueBytes() is { } bytes ? Encoding.UTF8.GetString(bytes) : "");
        }
        return JsonSerializer.Serialize(dict);
    }
}

internal class Consumer : IDisposable
{
    private const string TopicName = "orders";

    private readonly ILogger _logger;
    private readonly IConsumer<string, byte[]> _consumer;
    private bool _isListening;
    private readonly DBContext? _dbContext;
    private readonly SqlPostInsertPipeline _sqlPipeline;
    private static readonly ActivitySource MyActivitySource = new("Accounting.Consumer");
    private static readonly TextMapPropagator Propagator = Propagators.DefaultTextMapPropagator;

    public Consumer(ILogger<Consumer> logger)
    {
        _logger = logger;

        var servers = Environment.GetEnvironmentVariable("KAFKA_ADDR")
            ?? throw new ArgumentNullException("KAFKA_ADDR");

        _consumer = BuildConsumer(servers);
        _consumer.Subscribe(TopicName);
        _logger.LogInformation($"Connecting to Kafka: {servers}");

        var connStr = Environment.GetEnvironmentVariable("DB_CONNECTION_STRING");
        _dbContext = connStr == null ? null : new DBContext();

        // Make sure DB exists for demo purposes (you likely want proper migrations)
        _dbContext?.Database.EnsureCreated();

        // Build SQL pipeline (add more tasks here later)
        _sqlPipeline = new SqlPostInsertPipeline()
            .Add(new TodayMessagesSqlTask());
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

                    // Extract parent context from Kafka headers
                    var parentContext = Propagator.Extract(default, consumeResult.Message.Headers,
                        (headers, key) =>
                        {
                            return headers.TryGetLastBytes(key, out var value)
                                ? new[] { Encoding.UTF8.GetString(value) }
                                : Array.Empty<string>();
                        });

                    OpenTelemetry.Baggage.Current = parentContext.Baggage;

                    using var activity = MyActivitySource.StartActivity(
                        "order-consumed",
                        ActivityKind.Consumer,
                        parentContext.ActivityContext);

                    ProcessMessage(consumeResult.Message);
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
            _consumer.Close();
        }
    }

    private void ProcessMessage(Message<string, byte[]> message)
    {
        try
        {
            var order = OrderResult.Parser.ParseFrom(message.Value);
            Log.OrderReceivedMessage(_logger, order);

            if (_dbContext == null)
            {
                // DB not configured – just log and return
                return;
            }

            var utcNow = DateTime.UtcNow;

            // 1) Save your domain entities (existing behavior)
            var orderEntity = new OrderEntity { Id = order.OrderId };
            _dbContext.Add(orderEntity);

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
                _dbContext.Add(orderItem);
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
            _dbContext.Add(shipping);

            // 2) Also store the raw Kafka message (key, value, headers)
            var raw = new RawKafkaMessageEntity
            {
                Key = message.Key,
                Value = message.Value ?? Array.Empty<byte>(),
                HeadersJson = message.Headers != null ? KafkaHeaderSerializer.ToJson(message.Headers) : null,
                ReceivedAtUtc = utcNow
            };
            _dbContext.Add(raw);

            // 3) Save everything via EF first
            _dbContext.SaveChanges();

            // 4) Run the SQL pipeline (extensible hook for adding more SQL tasks)
            //    Use a single connection & transaction for deterministic behavior.
            var connStr = _dbContext.Database.GetConnectionString();
            using var conn = new SqlConnection(connStr);
            conn.Open();
           using var tx = conn.BeginTransaction(System.Data.IsolationLevel.ReadCommitted);

            _sqlPipeline.RunAll(conn, tx);

            tx.Commit();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Order processing failed:");
        }
    }

    private IConsumer<string, byte[]> BuildConsumer(string servers)
    {
        var conf = new ConsumerConfig
        {
            GroupId = "accounting",
            BootstrapServers = servers,
            AutoOffsetReset = AutoOffsetReset.Earliest,
            EnableAutoCommit = true
        };

        return new ConsumerBuilder<string, byte[]>(conf).Build();
    }

    public void Dispose()
    {
        _isListening = false;
        _consumer?.Dispose();
    }
}