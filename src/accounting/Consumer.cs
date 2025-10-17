using Confluent.Kafka;
using Microsoft.Extensions.Logging;
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
        var dbType = Environment.GetEnvironmentVariable("DB_TYPE")?.ToLowerInvariant();

        switch (dbType)
        {
            case "mysql":
                Console.WriteLine("[DBContext] Using MySQL provider");
                optionsBuilder.UseMySql(connectionString, ServerVersion.AutoDetect(connectionString))
                              .UseSnakeCaseNamingConvention();
                break;
            case "postgres":
            default:
                Console.WriteLine("[DBContext] Using Postgres provider [default]");
                optionsBuilder.UseNpgsql(connectionString)
                              .UseSnakeCaseNamingConvention();
                break;
        }
    }
}

internal class Consumer : IDisposable
{
    private const string TopicName = "orders";
    private readonly ILogger _logger;
    private readonly IConsumer<string, byte[]> _consumer;
    private bool _isListening;
    private static readonly ActivitySource MyActivitySource = new("Accounting.Consumer");
    private readonly DBContext? _dbContext;
    private readonly MongoDataService? _mongoService;
    private readonly string? _dbType;

    public Consumer(ILogger<Consumer> logger)
    {
        _logger = logger;
        _dbType = Environment.GetEnvironmentVariable("DB_TYPE")?.ToLowerInvariant();
        var connectionString = Environment.GetEnvironmentVariable("DB_CONNECTION_STRING");

        var servers = Environment.GetEnvironmentVariable("KAFKA_ADDR")
            ?? throw new ArgumentNullException("KAFKA_ADDR");

        _consumer = BuildConsumer(servers);
        _consumer.Subscribe(TopicName);
        _logger.LogInformation($"Connecting to Kafka: {servers}");

        if (connectionString != null)
        {
            switch (_dbType)
            {
                case "mongo":
                    _logger.LogInformation("Using MongoDB for data storage.");
                    try
                    {
                        _mongoService = new MongoDataService();
                    }
                    catch (Exception ex)
                    {
                        _logger.LogError(ex, "Failed to initialize MongoDB service.");
                        throw;
                    }
                    break;
                case "mysql":
                    _logger.LogInformation("Using relational database (mysql) for data storage.");
                    try
                    {
                        _dbContext = new DBContext();
                        _dbContext.Database.EnsureCreated();
                    }
                    catch (Exception ex)
                    {
                        _logger.LogError(ex, "Failed to initialize MySQL database.");
                        throw;
                    }
                    break;
                case "postgres":
                default:
                    _logger.LogInformation("Using relational database (postgres) for data storage. [default]");
                    try
                    {
                        _dbContext = new DBContext();
                    }
                    catch (Exception ex)
                    {
                        _logger.LogError(ex, "Failed to initialize PostgreSQL database.");
                        throw;
                    }
                    break;
            }
        }
        else
        {
            _logger.LogWarning("DB_CONNECTION_STRING is not set. Order data will not be persisted.");
        }
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
                    using var activity = MyActivitySource.StartActivity("order-consumed", ActivityKind.Internal);
                    var consumeResult = _consumer.Consume();
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

            if (_dbType == "mongo" && _mongoService != null)
            {
                try
                {
                    _mongoService.SaveOrderAsync(order).GetAwaiter().GetResult();
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "MongoDB order insert failed.");
                }
            }
            else if (_dbContext != null)
            {
                var dbService = _dbType == "mysql" ? "MySqlDataService" : "PostgresDataService";
                try
                {
                    _logger.LogInformation("[{DbService}] Attempting insert for OrderId={OrderId}", dbService, order.OrderId);

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
                    _dbContext.SaveChanges();

                    _logger.LogInformation("[{DbService}] Insert succeeded for OrderId={OrderId}", dbService, order.OrderId);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "[{DbService}] Insert FAILED for OrderId={OrderId}", dbService, order.OrderId);
                }
            }
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
            GroupId = $"accounting",
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