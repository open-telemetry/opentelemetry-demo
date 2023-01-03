package org.daocloud.springcloud.adservice.meter;

import io.opentelemetry.api.metrics.DoubleHistogram;
import io.opentelemetry.api.metrics.LongCounter;
import io.opentelemetry.api.metrics.MeterProvider;
import io.opentelemetry.exporter.prometheus.PrometheusHttpServer;
import io.opentelemetry.sdk.metrics.SdkMeterProvider;
import io.opentelemetry.sdk.metrics.export.MetricReader;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.stereotype.Component;

@Component
public final class Meter {

    private static final Logger logger = LogManager.getLogger(Meter.class);

    private final MeterProvider meterProvider;

    private final LongCounter grpcCalls;

    private final DoubleHistogram grpcLagency;



    /**
     * Initializes the Meter SDK and configures the prometheus collector with all default settings.
     *
     * @param prometheusPort the port to open up for scraping.
     * @return A MeterProvider for use in instrumentation.
     */
    public Meter(@Value("${meter.port}") int prometheusPort) {
        logger.info("prometheus export metrics at: 0.0.0.0:"+prometheusPort);
        MetricReader prometheusReader = PrometheusHttpServer.builder().setPort(prometheusPort).build();
        meterProvider = SdkMeterProvider.builder().registerMetricReader(prometheusReader).build();

        io.opentelemetry.api.metrics.Meter meter = meterProvider.get("adservice");
        grpcCalls = meter.counterBuilder("adservice_grpc_call")
                .setDescription("record grpc call totals")
                .build();

        grpcLagency = meter.histogramBuilder("adservice_grpc_duration_seconds")
                .setDescription("record grpc call latency histogram")
                .build();
    }

    public LongCounter getGrpcCalls() {
        return grpcCalls;
    }


    public DoubleHistogram getGrpcLagency() {
        return grpcLagency;
    }
}
