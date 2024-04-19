using Confluent.Kafka;
using Confluent.Kafka.SyncOverAsync;
using Confluent.SchemaRegistry.Serdes;
using Microsoft.Extensions.Logging;
using Oteldemo;

namespace AccountingService;

internal class Consumer : IDisposable
{
    private const string TopicName = "orders";

    private ILogger _logger;
    private IConsumer<string, OrderResult> _consumer;
    private bool _isListening;

    public Consumer(ILogger<Consumer> logger)
    {
        _logger = logger;

        var servers = Environment.GetEnvironmentVariable("KAFKA_SERVICE_ADDR")
            ?? throw new ArgumentNullException("KAFKA_SERVICE_ADDR");

        _consumer = BuildConsumer(servers);
        _consumer.Subscribe(TopicName);

        _logger.LogInformation($"Connecting to Kafka: {servers}");
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
                    if (consumeResult.IsPartitionEOF)
                    {
                        continue;
                    }

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

    private void ProcessMessage(Message<string, OrderResult> message)
    {
        Log.LogOrderReceivedMessage(_logger, message.Value);
    }

    private IConsumer<string, OrderResult> BuildConsumer(string servers)
    {
        var conf = new ConsumerConfig
        {
            GroupId = $"accountingservice",
            BootstrapServers = servers,
            // https://github.com/confluentinc/confluent-kafka-dotnet/tree/07de95ed647af80a0db39ce6a8891a630423b952#basic-consumer-example
            AutoOffsetReset = AutoOffsetReset.Earliest,
            CancellationDelayMaxMs = 10_000,
            EnableAutoCommit = true
        };

        return new ConsumerBuilder<string, OrderResult>(conf)
            .SetValueDeserializer(new ProtobufDeserializer<OrderResult>().AsSyncOverAsync())
            .Build();
    }

    public void Dispose()
    {
        _isListening = false;
        _consumer?.Dispose();
    }
}
