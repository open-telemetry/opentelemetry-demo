/*
* Copyright The OpenTelemetry Authors
* SPDX-License-Identifier: Apache-2.0
*/
package businessmetricservice;

import io.opentelemetry.api.GlobalOpenTelemetry;
import io.opentelemetry.api.metrics.MeterProvider;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;

@SpringBootApplication
public class BusinessMetricServiceApplication {

    public static void main(String[] args) {
        SpringApplication.run(BusinessMetricServiceApplication.class, args);
    }

    @Bean
    public MeterProvider meterProvider() {
        return GlobalOpenTelemetry.getMeterProvider();
    }
}