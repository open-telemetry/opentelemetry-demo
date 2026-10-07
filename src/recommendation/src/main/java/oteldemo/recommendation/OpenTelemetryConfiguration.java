/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */

package oteldemo.recommendation;

import io.opentelemetry.api.GlobalOpenTelemetry;
import io.opentelemetry.api.OpenTelemetry;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration(proxyBeanMethods = false)
class OpenTelemetryConfiguration {

  // The Java agent sets up the SDK and registers it as the global instance.
  @Bean
  OpenTelemetry openTelemetry() {
    return GlobalOpenTelemetry.get();
  }
}
