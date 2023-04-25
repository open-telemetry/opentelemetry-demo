package businessmetricservice;

import io.opentelemetry.api.metrics.Meter;
import io.opentelemetry.api.metrics.MeterProvider;
import io.opentelemetry.api.metrics.LongCounter;
import io.opentelemetry.api.common.Attributes;
import io.opentelemetry.api.common.AttributeKey;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Service;
import oteldemo.Demo.OrderItem;
import oteldemo.Demo.OrderResult;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;


@Service
public class KafkaOrderResultConsumer {

    private final Meter meter;
    private final LongCounter appBusinessMetricsProducts;
    private static final AttributeKey<String> PRODUCT_ID = AttributeKey.stringKey("product_id");

    private static final Logger logger = LoggerFactory.getLogger(KafkaOrderResultConsumer.class);

    public KafkaOrderResultConsumer(MeterProvider meterProvider) {
        this.meter = meterProvider.get("OrderResultConsumer");
        this.appBusinessMetricsProducts = meter.counterBuilder("app.businessmetrics.products")
                .setDescription("Product metrics")
                .setUnit("1")
                .build();
    }

    @KafkaListener(topics = "orders", groupId = "businessMetricGroup")
    public void consumeOrderResult(byte[] orderResultBytes) {
        try {
            OrderResult orderResult = OrderResult.parseFrom(orderResultBytes);
            logger.info("Received OrderResult: {}", orderResult);

            for (OrderItem orderItem : orderResult.getItemsList()) {
                String productId = orderItem.getItem().getProductId();
                appBusinessMetricsProducts.add(1, Attributes.of(PRODUCT_ID, productId));
            }
        } catch (Exception e) {
            System.out.println("Error while consuming message: " + e.getMessage());
        }
    }
}
