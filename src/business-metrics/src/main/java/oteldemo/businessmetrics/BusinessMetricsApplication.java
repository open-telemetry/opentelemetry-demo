/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */

package oteldemo.businessmetrics;

import com.google.protobuf.InvalidProtocolBufferException;
import io.opentelemetry.api.GlobalOpenTelemetry;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.Properties;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.logging.Level;
import java.util.logging.Logger;
import org.apache.kafka.clients.consumer.Consumer;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.common.errors.WakeupException;
import org.apache.kafka.common.serialization.ByteArrayDeserializer;
import org.apache.kafka.common.serialization.StringDeserializer;
import oteldemo.Demo.OrderResult;

public final class BusinessMetricsApplication {
  private static final Logger logger = Logger.getLogger(BusinessMetricsApplication.class.getName());

  private BusinessMetricsApplication() {}

  public static void main(String[] args) {
    var consumer = new KafkaConsumer<String, byte[]>(consumerProperties(System.getenv()));
    var running = new AtomicBoolean(true);
    Runtime.getRuntime().addShutdownHook(new Thread(() -> {
      running.set(false);
      consumer.wakeup();
    }));
    var metrics = new OrderMetrics(GlobalOpenTelemetry.get());
    try (consumer) {
      consumer.subscribe(List.of(System.getenv().getOrDefault("KAFKA_TOPIC", "orders")));
      while (running.get()) {
        pollAndRecord(consumer, metrics);
      }
    } catch (WakeupException e) {
      if (running.get()) {
        throw e;
      }
    }
  }

  static Properties consumerProperties(Map<String, String> environment) {
    var properties = new Properties();
    properties.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG,
        environment.getOrDefault("KAFKA_ADDR", "kafka:9092"));
    properties.put(ConsumerConfig.GROUP_ID_CONFIG, "business-metrics");
    properties.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
    properties.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, ByteArrayDeserializer.class.getName());
    properties.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");
    properties.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, "false");
    return properties;
  }

  static void pollAndRecord(Consumer<String, byte[]> consumer, OrderMetrics metrics) {
    var records = consumer.poll(Duration.ofSeconds(1));
    for (var record : records) {
      if (record.value() == null) {
        continue;
      }
      try {
        metrics.record(OrderResult.parseFrom(record.value()));
        logger.info("Processed order");
      } catch (InvalidProtocolBufferException | IllegalArgumentException e) {
        logger.log(Level.WARNING, "Skipping invalid order at " + record.topic() + ":"
            + record.partition() + ":" + record.offset(), e);
      }
    }
    if (!records.isEmpty()) {
      consumer.commitSync();
    }
  }
}
