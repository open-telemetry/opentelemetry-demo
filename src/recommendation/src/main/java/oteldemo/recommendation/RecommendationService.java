/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */

package oteldemo.recommendation;

import dev.openfeature.sdk.Client;
import io.grpc.stub.StreamObserver;
import io.opentelemetry.api.OpenTelemetry;
import io.opentelemetry.api.common.AttributeKey;
import io.opentelemetry.api.common.Attributes;
import io.opentelemetry.api.metrics.LongCounter;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.StatusCode;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.context.Scope;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.ThreadLocalRandom;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import oteldemo.Demo.Empty;
import oteldemo.Demo.ListRecommendationsRequest;
import oteldemo.Demo.ListRecommendationsResponse;
import oteldemo.Demo.Product;
import oteldemo.ProductCatalogServiceGrpc.ProductCatalogServiceBlockingStub;
import oteldemo.RecommendationServiceGrpc;

@Service
public class RecommendationService extends RecommendationServiceGrpc.RecommendationServiceImplBase {

  private static final Logger logger = LoggerFactory.getLogger(RecommendationService.class);

  private static final String CACHE_FAILURE_FLAG = "recommendationCacheFailure";
  private static final int MAX_RESPONSES = 5;
  private static final AttributeKey<List<String>> FILTERED_LIST =
      AttributeKey.stringArrayKey("demo.product.filtered.list");
  private static final Attributes CATALOG_RECOMMENDATION =
      Attributes.of(AttributeKey.stringKey("recommendation.type"), "catalog");

  private final ProductCatalogServiceBlockingStub productCatalog;
  private final Client featureFlags;
  private final Tracer tracer;
  private final LongCounter recommendations;

  private final List<String> cachedIds = new ArrayList<>();
  private boolean firstRun = true;

  public RecommendationService(
      ProductCatalogServiceBlockingStub productCatalog,
      Client featureFlags,
      OpenTelemetry openTelemetry) {
    this.productCatalog = productCatalog;
    this.featureFlags = featureFlags;
    this.tracer = openTelemetry.getTracer("recommendation");
    this.recommendations =
        openTelemetry
            .getMeter("recommendation")
            .counterBuilder("demo.recommendation.requests")
            .setDescription("Counts the total number of given recommendations")
            .setUnit("{recommendation}")
            .build();
  }

  @Override
  public void listRecommendations(
      ListRecommendationsRequest request,
      StreamObserver<ListRecommendationsResponse> responseObserver) {
    List<String> productIds = getProductList(request.getProductIdsList());
    Span.current().setAttribute("demo.product.recommended.count", productIds.size());
    logger.info("Receive ListRecommendations for product ids:{}", productIds);
    recommendations.add(productIds.size(), CATALOG_RECOMMENDATION);

    responseObserver.onNext(
        ListRecommendationsResponse.newBuilder().addAllProductIds(productIds).build());
    responseObserver.onCompleted();
  }

  private List<String> getProductList(List<String> requestProductIds) {
    Span span = tracer.spanBuilder("get_product_list").startSpan();
    try (Scope ignored = span.makeCurrent()) {
      Products products;
      if (featureFlags.getBooleanValue(CACHE_FAILURE_FLAG, false)) {
        span.setAttribute("demo.feature_flag.recommendation_cache", true);
        products = getProductsFromLeakyCache(span);
      } else {
        span.setAttribute("demo.feature_flag.recommendation_cache", false);
        List<String> fresh = fetchProductIds();
        products = new Products(fresh.size(), new HashSet<>(fresh));
      }
      span.setAttribute("demo.product.count", products.count());

      List<String> filtered = new ArrayList<>(products.unique());
      filtered.removeAll(requestedIds(requestProductIds));
      span.setAttribute("demo.product.filtered.count", filtered.size());

      Collections.shuffle(filtered, ThreadLocalRandom.current());
      List<String> recommended =
          List.copyOf(filtered.subList(0, Math.min(MAX_RESPONSES, filtered.size())));
      span.setAttribute(FILTERED_LIST, recommended);
      return recommended;
    } catch (RuntimeException e) {
      span.recordException(e);
      span.setStatus(StatusCode.ERROR);
      throw e;
    } finally {
      span.end();
    }
  }

  // The frontend sends the ids as one repeated element per character: its API route
  // (src/frontend/pages/api/recommendations.ts) hands the comma-joined query string to the
  // gRPC client as if it were an array. Those elements are joined back together before
  // splitting on the commas between ids. A client that sends whole ids still works.
  private static Set<String> requestedIds(List<String> requestProductIds) {
    boolean oneCharacterEach =
        !requestProductIds.isEmpty()
            && requestProductIds.stream().allMatch(id -> id.length() == 1);
    String joined = String.join(oneCharacterEach ? "" : ",", requestProductIds);
    return new HashSet<>(List.of(joined.split(",")));
  }

  // Simulates the memory leak behind the recommendationCacheFailure feature flag: every
  // cache miss appends the catalog plus a quarter of the cache to itself.
  private Products getProductsFromLeakyCache(Span span) {
    boolean miss;
    synchronized (cachedIds) {
      miss = firstRun || ThreadLocalRandom.current().nextDouble() < 0.5;
      firstRun = false;
    }
    if (miss) {
      span.setAttribute("demo.recommendation.cache_hit", false);
      logger.info("get_product_list: cache miss");
      List<String> fresh = fetchProductIds();
      synchronized (cachedIds) {
        cachedIds.addAll(fresh);
        cachedIds.addAll(new ArrayList<>(cachedIds.subList(0, cachedIds.size() / 4)));
        return new Products(cachedIds.size(), new HashSet<>(cachedIds));
      }
    }
    span.setAttribute("demo.recommendation.cache_hit", true);
    logger.info("get_product_list: cache hit");
    synchronized (cachedIds) {
      return new Products(cachedIds.size(), new HashSet<>(cachedIds));
    }
  }

  private List<String> fetchProductIds() {
    return productCatalog.listProducts(Empty.getDefaultInstance()).getProductsList().stream()
        .map(Product::getId)
        .toList();
  }

  private record Products(int count, Set<String> unique) {}
}
