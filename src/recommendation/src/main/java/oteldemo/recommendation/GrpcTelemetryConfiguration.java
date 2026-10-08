/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */

package oteldemo.recommendation;

import io.grpc.ClientInterceptor;
import io.grpc.ServerInterceptor;
import io.opentelemetry.api.OpenTelemetry;
import io.opentelemetry.instrumentation.grpc.v1_6.GrpcTelemetry;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.grpc.client.GlobalClientInterceptor;
import org.springframework.grpc.server.GlobalServerInterceptor;

@Configuration(proxyBeanMethods = false)
class GrpcTelemetryConfiguration {

  @Bean
  GrpcTelemetry grpcTelemetry(OpenTelemetry openTelemetry) {
    return GrpcTelemetry.create(openTelemetry);
  }

  @Bean
  @GlobalServerInterceptor
  ServerInterceptor grpcTelemetryServerInterceptor(GrpcTelemetry grpcTelemetry) {
    return grpcTelemetry.createServerInterceptor();
  }

  @Bean
  @GlobalClientInterceptor
  ClientInterceptor grpcTelemetryClientInterceptor(GrpcTelemetry grpcTelemetry) {
    return grpcTelemetry.createClientInterceptor();
  }
}
