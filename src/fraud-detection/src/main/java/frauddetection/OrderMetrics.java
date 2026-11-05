/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */

package frauddetection;

import io.opentelemetry.api.OpenTelemetry;
import io.opentelemetry.api.common.AttributeKey;
import io.opentelemetry.api.common.Attributes;
import io.opentelemetry.api.metrics.DoubleCounter;
import io.opentelemetry.api.metrics.LongCounter;
import java.util.HashMap;
import java.util.Map;
import oteldemo.Demo.Money;
import oteldemo.Demo.OrderItem;
import oteldemo.Demo.OrderResult;

final class OrderMetrics {
  private final LongCounter orders;
  private final DoubleCounter sales;

  OrderMetrics(OpenTelemetry telemetry) {
    var meter = telemetry.getMeter("fraud-detection");
    orders = meter.counterBuilder("demo.business.orders")
        .setDescription("Number of processed orders")
        .setUnit("{order}")
        .build();
    sales = meter.counterBuilder("demo.business.sales")
        .ofDoubles()
        .setDescription("Value of ordered products, excluding shipping")
        .setUnit("{currency}")
        .build();
  }

  void record(OrderResult order) {
    if (order.getOrderId().isBlank()) {
      throw new IllegalArgumentException("Order has no id");
    }
    Map<String, Double> totals = new HashMap<>();
    for (OrderItem item : order.getItemsList()) {
      Money cost = item.getCost();
      int quantity = item.getItem().getQuantity();
      if (quantity < 0 || cost.getUnits() < 0 || cost.getNanos() < 0
          || cost.getNanos() >= 1_000_000_000 || cost.getCurrencyCode().isBlank()) {
        throw new IllegalArgumentException("Order has an invalid price or quantity");
      }
      double amount = (cost.getUnits() + cost.getNanos() / 1_000_000_000.0) * quantity;
      totals.merge(cost.getCurrencyCode(), amount, Double::sum);
    }
    totals.forEach((currency, amount) -> sales.add(amount,
        Attributes.of(AttributeKey.stringKey("currency"), currency)));
    orders.add(1);
  }
}
