/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */

package oteldemo.recommendation;

import dev.openfeature.contrib.hooks.otel.TracesHook;
import dev.openfeature.contrib.providers.flagd.FlagdOptions;
import dev.openfeature.contrib.providers.flagd.FlagdProvider;
import dev.openfeature.sdk.Client;
import dev.openfeature.sdk.FeatureProvider;
import dev.openfeature.sdk.OpenFeatureAPI;
import io.opentelemetry.api.OpenTelemetry;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration(proxyBeanMethods = false)
class FeatureFlagConfiguration {

  @Bean
  FeatureProvider flagdProvider(OpenTelemetry openTelemetry) {
    return new FlagdProvider(FlagdOptions.builder().openTelemetry(openTelemetry).build());
  }

  @Bean
  Client featureFlagClient(FeatureProvider featureProvider) {
    OpenFeatureAPI api = OpenFeatureAPI.getInstance();
    api.setProvider(featureProvider);
    api.addHooks(new TracesHook());
    return api.getClient();
  }
}
