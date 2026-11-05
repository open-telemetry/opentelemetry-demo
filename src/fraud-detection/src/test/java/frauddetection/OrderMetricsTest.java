/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */

package frauddetection;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import io.opentelemetry.api.common.AttributeKey;
import io.opentelemetry.sdk.OpenTelemetrySdk;
import io.opentelemetry.sdk.metrics.SdkMeterProvider;
import io.opentelemetry.sdk.testing.exporter.InMemoryMetricReader;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import oteldemo.Demo.CartItem;
import oteldemo.Demo.Money;
import oteldemo.Demo.OrderItem;
import oteldemo.Demo.OrderResult;

class OrderMetricsTest {
  private final InMemoryMetricReader reader = InMemoryMetricReader.create();
  private final SdkMeterProvider provider = SdkMeterProvider.builder()
      .registerMetricReader(reader).build();
  private final OrderMetrics metrics = new OrderMetrics(
      OpenTelemetrySdk.builder().setMeterProvider(provider).build());

  @AfterEach
  void close() {
    provider.close();
  }

  @Test
  void countsOrdersAndMultipliesPricesByQuantitiesWithoutShipping() {
    metrics.record(OrderResult.newBuilder().setOrderId("order-1")
        .addItems(item("USD", 12, 500_000_000, 3))
        .addItems(item("USD", 2, 250_000_000, 2))
        .setShippingCost(Money.newBuilder().setCurrencyCode("USD").setUnits(10))
        .build());
    metrics.record(OrderResult.newBuilder().setOrderId("order-2")
        .addItems(item("USD", 0, 125_000_000, 2)).build());

    assertEquals(2, orders());
    assertEquals(42.25, sales("USD"), 0.000001);
  }

  @Test
  void keepsCurrenciesInSeparateSeries() {
    metrics.record(OrderResult.newBuilder().setOrderId("order-1")
        .addItems(item("USD", 4, 0, 2))
        .addItems(item("EUR", 3, 500_000_000, 3)).build());

    assertEquals(8.0, sales("USD"));
    assertEquals(10.5, sales("EUR"));
    assertEquals(2, reader.collectAllMetrics().stream()
        .filter(metric -> metric.getName().equals("demo.business.sales"))
        .findFirst().orElseThrow().getDoubleSumData().getPoints().size());
  }

  @Test
  void rejectsInvalidOrdersBeforeRecordingAnyMetrics() {
    assertThrows(IllegalArgumentException.class,
        () -> metrics.record(OrderResult.getDefaultInstance()));
    assertThrows(IllegalArgumentException.class,
        () -> metrics.record(OrderResult.newBuilder().setOrderId("order-1")
            .addItems(item("USD", 1, 0, 1))
            .addItems(item("USD", 1, 0, -1)).build()));
    assertThrows(IllegalArgumentException.class,
        () -> metrics.record(OrderResult.newBuilder().setOrderId("order-2")
            .addItems(item("", 1, 0, 1)).build()));
    assertThrows(IllegalArgumentException.class,
        () -> metrics.record(OrderResult.newBuilder().setOrderId("order-3")
            .addItems(item("USD", 1, 1_000_000_000, 1)).build()));
    assertEquals(0, orders());
    assertEquals(0, reader.collectAllMetrics().size());
  }

  private static OrderItem item(String currency, long units, int nanos, int quantity) {
    return OrderItem.newBuilder()
        .setItem(CartItem.newBuilder().setProductId("product-1").setQuantity(quantity))
        .setCost(Money.newBuilder().setCurrencyCode(currency).setUnits(units).setNanos(nanos))
        .build();
  }

  private long orders() {
    return reader.collectAllMetrics().stream()
        .filter(metric -> metric.getName().equals("demo.business.orders"))
        .flatMap(metric -> metric.getLongSumData().getPoints().stream())
        .mapToLong(point -> point.getValue()).sum();
  }

  private double sales(String currency) {
    return reader.collectAllMetrics().stream()
        .filter(metric -> metric.getName().equals("demo.business.sales"))
        .flatMap(metric -> metric.getDoubleSumData().getPoints().stream())
        .filter(point -> currency.equals(point.getAttributes().get(AttributeKey.stringKey("currency"))))
        .mapToDouble(point -> point.getValue()).sum();
  }
}
