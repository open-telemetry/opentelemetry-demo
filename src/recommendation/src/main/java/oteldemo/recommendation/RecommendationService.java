/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */

package oteldemo.recommendation;

import dev.openfeature.sdk.Client;
import io.grpc.stub.StreamObserver;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.tracing.Span;
import io.micrometer.tracing.Tracer;
import io.opentelemetry.api.common.AttributeKey;
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

  private final ProductCatalogServiceBlockingStub productCatalog;
  private final Client featureFlags;
  private final Tracer tracer;
  private final Counter recommendations;

  private final List<String> cachedIds = new ArrayList<>();
  private boolean firstRun = true;

  public RecommendationService(
      ProductCatalogServiceBlockingStub productCatalog,
      Client featureFlags,
      Tracer tracer,
      MeterRegistry meterRegistry) {
    this.productCatalog = productCatalog;
    this.featureFlags = featureFlags;
    this.tracer = tracer;
    this.recommendations =
        Counter.builder("demo.recommendation.requests")
            .description("Counts the total number of given recommendations")
            .baseUnit("{recommendation}")
            .tag("recommendation.type", "catalog")
            .register(meterRegistry);
  }

  @Override
  public void listRecommendations(
      ListRecommendationsRequest request,
      StreamObserver<ListRecommendationsResponse> responseObserver) {
    List<String> productIds = getProductList(request.getProductIdsList());
    Span span = tracer.currentSpan();
    if (span != null) {
      span.tag("demo.product.recommended.count", productIds.size());
    }
    logger.info("Receive ListRecommendations for product ids:{}", productIds);
    recommendations.increment(productIds.size());

    responseObserver.onNext(
        ListRecommendationsResponse.newBuilder().addAllProductIds(productIds).build());
    responseObserver.onCompleted();
  }

  private List<String> getProductList(List<String> requestProductIds) {
    Span span = tracer.nextSpan().name("get_product_list").start();
    try (Tracer.SpanInScope ignored = tracer.withSpan(span)) {
      Products products;
      if (featureFlags.getBooleanValue(CACHE_FAILURE_FLAG, false)) {
        span.tag("demo.feature_flag.recommendation_cache", true);
        products = getProductsFromLeakyCache(span);
      } else {
        span.tag("demo.feature_flag.recommendation_cache", false);
        List<String> fresh = fetchProductIds();
        products = new Products(fresh.size(), new HashSet<>(fresh));
      }
      span.tag("demo.product.count", products.count());

      List<String> filtered = new ArrayList<>(products.unique());
      filtered.removeAll(requestedIds(requestProductIds));
      span.tag("demo.product.filtered.count", filtered.size());

      Collections.shuffle(filtered, ThreadLocalRandom.current());
      List<String> recommended =
          List.copyOf(filtered.subList(0, Math.min(MAX_RESPONSES, filtered.size())));
      // Micrometer spans only take scalar tags, so the array attribute is set through the
      // OpenTelemetry API on the same span.
      io.opentelemetry.api.trace.Span.current().setAttribute(FILTERED_LIST, recommended);
      return recommended;
    } catch (RuntimeException e) {
      span.error(e);
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
      span.tag("demo.recommendation.cache_hit", false);
      logger.info("get_product_list: cache miss");
      List<String> fresh = fetchProductIds();
      synchronized (cachedIds) {
        cachedIds.addAll(fresh);
        cachedIds.addAll(new ArrayList<>(cachedIds.subList(0, cachedIds.size() / 4)));
        return new Products(cachedIds.size(), new HashSet<>(cachedIds));
      }
    }
    span.tag("demo.recommendation.cache_hit", true);
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
