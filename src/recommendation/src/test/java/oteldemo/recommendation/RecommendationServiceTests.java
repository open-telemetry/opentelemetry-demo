/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */

package oteldemo.recommendation;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.awaitility.Awaitility.await;

import dev.openfeature.sdk.OpenFeatureAPI;
import dev.openfeature.sdk.providers.memory.Flag;
import dev.openfeature.sdk.providers.memory.InMemoryProvider;
import io.grpc.BindableService;
import io.grpc.Status;
import io.grpc.StatusRuntimeException;
import io.grpc.stub.StreamObserver;
import io.micrometer.core.instrument.MeterRegistry;
import io.opentelemetry.api.common.AttributeKey;
import io.opentelemetry.api.trace.SpanKind;
import io.opentelemetry.api.trace.StatusCode;
import io.opentelemetry.sdk.testing.exporter.InMemorySpanExporter;
import io.opentelemetry.sdk.trace.SpanProcessor;
import io.opentelemetry.sdk.trace.data.SpanData;
import io.opentelemetry.sdk.trace.export.SimpleSpanProcessor;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.grpc.test.autoconfigure.AutoConfigureTestGrpcTransport;
import org.springframework.boot.micrometer.tracing.test.autoconfigure.AutoConfigureTracing;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.grpc.client.GrpcChannelFactory;
import oteldemo.Demo.Empty;
import oteldemo.Demo.ListProductsResponse;
import oteldemo.Demo.ListRecommendationsRequest;
import oteldemo.Demo.ListRecommendationsResponse;
import oteldemo.Demo.Product;
import oteldemo.ProductCatalogServiceGrpc;
import oteldemo.RecommendationServiceGrpc;

@SpringBootTest
@AutoConfigureTestGrpcTransport
@AutoConfigureTracing
class RecommendationServiceTests {

  private static final String CACHE_FAILURE_FLAG = "recommendationCacheFailure";
  private static final List<String> CATALOG =
      List.of("0PUK6V6EV0", "1YMWWN1N4O", "2ZYFJ3GM2N", "66VCHSJNUP", "6E92ZMJLZN", "9SOIN3QJO0", "L9ECAV7KIM");
  private static final AtomicBoolean CATALOG_DOWN = new AtomicBoolean(false);

  @Autowired private GrpcChannelFactory channels;
  @Autowired private InMemorySpanExporter spans;
  @Autowired private MeterRegistry meterRegistry;
  @Autowired private InMemoryProvider featureFlags;

  @BeforeEach
  void setUp() {
    OpenFeatureAPI.getInstance().setProviderAndWait(featureFlags);
    setCacheFailureFlag(false);
    spans.reset();
  }

  @AfterEach
  void tearDown() {
    setCacheFailureFlag(false);
  }

  @Test
  void recommendsUpToFiveOtherProducts() {
    ListRecommendationsResponse response = listRecommendations("66VCHSJNUP");

    assertThat(response.getProductIdsList())
        .hasSize(5)
        .doesNotHaveDuplicates()
        .doesNotContain("66VCHSJNUP")
        .isSubsetOf(CATALOG);
  }

  @Test
  void leavesOutEveryRequestedProductSentTheWayTheFrontendSendsThem() {
    List<String> oneElementPerCharacter =
        "66VCHSJNUP,0PUK6V6EV0,1YMWWN1N4O,2ZYFJ3GM2N".chars().mapToObj(c -> String.valueOf((char) c)).toList();

    ListRecommendationsResponse response = listRecommendations(oneElementPerCharacter);

    assertThat(response.getProductIdsList())
        .containsExactlyInAnyOrder("6E92ZMJLZN", "9SOIN3QJO0", "L9ECAV7KIM");
  }

  @Test
  void leavesOutEveryRequestedProductSentAsWholeIds() {
    ListRecommendationsResponse response =
        listRecommendations(List.of("66VCHSJNUP", "0PUK6V6EV0,1YMWWN1N4O", "2ZYFJ3GM2N"));

    assertThat(response.getProductIdsList())
        .containsExactlyInAnyOrder("6E92ZMJLZN", "9SOIN3QJO0", "L9ECAV7KIM");
  }

  @Test
  void recordsTheErrorWhenTheCatalogIsDown() {
    CATALOG_DOWN.set(true);
    try {
      assertThatThrownBy(() -> listRecommendations("66VCHSJNUP"))
          .isInstanceOf(StatusRuntimeException.class)
          .hasMessageContaining("UNAVAILABLE");
    } finally {
      CATALOG_DOWN.set(false);
    }

    SpanData productList = spanNamed("get_product_list", SpanKind.INTERNAL);
    assertThat(productList.getStatus().getStatusCode()).isEqualTo(StatusCode.ERROR);
    assertThat(productList.getEvents()).anyMatch(event -> event.getName().equals("exception"));
  }

  @Test
  void recordsSpanAttributesAndCounter() {
    double before = recommendationsCounted();

    listRecommendations("66VCHSJNUP");

    SpanData serverSpan = spanNamed("oteldemo.RecommendationService/ListRecommendations", SpanKind.SERVER);
    assertThat(serverSpan.getAttributes().get(AttributeKey.longKey("demo.product.recommended.count")))
        .isEqualTo(5L);

    SpanData productList = spanNamed("get_product_list", SpanKind.INTERNAL);
    assertThat(productList.getParentSpanId()).isEqualTo(serverSpan.getSpanId());
    assertThat(productList.getAttributes().get(AttributeKey.booleanKey("demo.feature_flag.recommendation_cache")))
        .isFalse();
    assertThat(productList.getAttributes().get(AttributeKey.longKey("demo.product.count"))).isEqualTo(7L);
    assertThat(productList.getAttributes().get(AttributeKey.longKey("demo.product.filtered.count")))
        .isEqualTo(6L);
    assertThat(productList.getAttributes().get(AttributeKey.stringArrayKey("demo.product.filtered.list")))
        .hasSize(5)
        .isSubsetOf(CATALOG);

    SpanData catalogCall = spanNamed("oteldemo.ProductCatalogService/ListProducts", SpanKind.CLIENT);
    assertThat(catalogCall.getTraceId()).isEqualTo(serverSpan.getTraceId());

    assertThat(recommendationsCounted()).isEqualTo(before + 5);
  }

  @Test
  void leakyCacheGrowsWhileTheFeatureFlagIsOn() {
    setCacheFailureFlag(true);

    listRecommendations("66VCHSJNUP");

    SpanData firstCall = spanNamed("get_product_list", SpanKind.INTERNAL);
    assertThat(firstCall.getAttributes().get(AttributeKey.booleanKey("demo.feature_flag.recommendation_cache")))
        .isTrue();
    assertThat(firstCall.getAttributes().get(AttributeKey.booleanKey("demo.recommendation.cache_hit")))
        .isFalse();
    assertThat(firstCall.getAttributes().get(AttributeKey.longKey("demo.product.count"))).isEqualTo(8L);

    spans.reset();
    listRecommendations("66VCHSJNUP");

    SpanData secondCall = spanNamed("get_product_list", SpanKind.INTERNAL);
    assertThat(secondCall.getAttributes().get(AttributeKey.booleanKey("demo.recommendation.cache_hit")))
        .isNotNull();
    assertThat(secondCall.getAttributes().get(AttributeKey.longKey("demo.product.count")))
        .isGreaterThanOrEqualTo(8L);
  }

  private ListRecommendationsResponse listRecommendations(String... productIds) {
    return listRecommendations(List.of(productIds));
  }

  private ListRecommendationsResponse listRecommendations(List<String> productIds) {
    return RecommendationServiceGrpc.newBlockingStub(channels.createChannel("recommendation"))
        .listRecommendations(
            ListRecommendationsRequest.newBuilder()
                .setUserId("test-user")
                .addAllProductIds(productIds)
                .build());
  }

  // The server span ends after the client already has its response, so give it a moment.
  private SpanData spanNamed(String name, SpanKind kind) {
    return await()
        .atMost(5, TimeUnit.SECONDS)
        .until(() -> findSpan(name, kind), Optional::isPresent)
        .orElseThrow();
  }

  private Optional<SpanData> findSpan(String name, SpanKind kind) {
    return spans.getFinishedSpanItems().stream()
        .filter(span -> span.getName().equals(name) && span.getKind() == kind)
        .findFirst();
  }

  private double recommendationsCounted() {
    return meterRegistry.get("demo.recommendation.requests").tag("recommendation.type", "catalog").counter().count();
  }

  private void setCacheFailureFlag(boolean enabled) {
    Map<String, Flag<?>> flags = new HashMap<>();
    flags.put(
        CACHE_FAILURE_FLAG,
        Flag.<Boolean>builder()
            .variant("on", true)
            .variant("off", false)
            .defaultVariant(enabled ? "on" : "off")
            .build());
    featureFlags.updateFlags(flags);
  }

  @TestConfiguration(proxyBeanMethods = false)
  static class TestConfig {

    @Bean
    InMemorySpanExporter inMemorySpanExporter() {
      return InMemorySpanExporter.create();
    }

    @Bean
    SpanProcessor inMemorySpanProcessor(InMemorySpanExporter exporter) {
      return SimpleSpanProcessor.create(exporter);
    }

    @Bean
    @Primary
    InMemoryProvider inMemoryFeatureProvider() {
      return new InMemoryProvider(new HashMap<>());
    }

    @Bean
    BindableService fakeProductCatalog() {
      return new ProductCatalogServiceGrpc.ProductCatalogServiceImplBase() {
        @Override
        public void listProducts(Empty request, StreamObserver<ListProductsResponse> responseObserver) {
          if (CATALOG_DOWN.get()) {
            responseObserver.onError(
                Status.UNAVAILABLE.withDescription("catalog down").asRuntimeException());
            return;
          }
          ListProductsResponse.Builder response = ListProductsResponse.newBuilder();
          CATALOG.forEach(id -> response.addProducts(Product.newBuilder().setId(id).setName(id)));
          responseObserver.onNext(response.build());
          responseObserver.onCompleted();
        }
      };
    }
  }
}
