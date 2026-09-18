/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */

package oteldemo.recommendation;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.grpc.client.ImportGrpcClients;
import oteldemo.ProductCatalogServiceGrpc.ProductCatalogServiceBlockingStub;

@SpringBootApplication
@ImportGrpcClients(target = "product-catalog", types = ProductCatalogServiceBlockingStub.class)
public class RecommendationApplication {

  public static void main(String[] args) {
    SpringApplication.run(RecommendationApplication.class, args);
  }
}
