/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */

package oteldemo.businessmetrics;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;

import io.opentelemetry.sdk.OpenTelemetrySdk;
import io.opentelemetry.sdk.metrics.SdkMeterProvider;
import io.opentelemetry.sdk.testing.exporter.InMemoryMetricReader;
import java.util.List;
import java.util.Map;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.clients.consumer.MockConsumer;
import org.apache.kafka.clients.consumer.OffsetResetStrategy;
import org.apache.kafka.common.TopicPartition;
import org.junit.jupiter.api.Test;
import oteldemo.Demo.OrderResult;

class BusinessMetricsApplicationTest {
  @Test
  void usesAnIndependentGroupAndCommitsAfterProcessing() {
    var properties = BusinessMetricsApplication.consumerProperties(Map.of("KAFKA_ADDR", "broker:19092"));
    assertEquals("broker:19092", properties.get(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG));
    assertEquals("business-metrics", properties.get(ConsumerConfig.GROUP_ID_CONFIG));
    assertEquals("false", properties.get(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG));
    assertEquals("earliest", properties.get(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG));
  }

  @Test
  void skipsMalformedMessagesAndTombstonesThenProcessesTheNextOrder() {
    var reader = InMemoryMetricReader.create();
    try (var provider = SdkMeterProvider.builder().registerMetricReader(reader).build();
        var consumer = new MockConsumer<String, byte[]>(OffsetResetStrategy.EARLIEST)) {
      var metrics = new OrderMetrics(OpenTelemetrySdk.builder().setMeterProvider(provider).build());
      var partition = new TopicPartition("orders", 0);
      consumer.subscribe(List.of("orders"));
      consumer.rebalance(List.of(partition));
      consumer.updateBeginningOffsets(Map.of(partition, 0L));
      consumer.addRecord(new ConsumerRecord<>("orders", 0, 0, "key", new byte[]{(byte) 0xff}));
      consumer.addRecord(new ConsumerRecord<>("orders", 0, 1, "key", null));
      consumer.addRecord(new ConsumerRecord<>("orders", 0, 2, "key", new byte[0]));
      consumer.addRecord(new ConsumerRecord<>("orders", 0, 3, "key",
          OrderResult.newBuilder().setOrderId("order-1").build().toByteArray()));

      BusinessMetricsApplication.pollAndRecord(consumer, metrics);

      assertEquals(4, consumer.committed(java.util.Set.of(partition)).get(partition).offset());
      var points = reader.collectAllMetrics().stream()
          .filter(metric -> metric.getName().equals("demo.business.orders"))
          .findFirst().orElseThrow().getLongSumData().getPoints();
      assertEquals(1, points.iterator().next().getValue());
      assertFalse(consumer.closed());
    }
  }
}
