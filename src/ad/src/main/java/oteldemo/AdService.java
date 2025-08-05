/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */

package oteldemo;

import com.google.common.collect.ImmutableListMultimap;
import com.google.common.collect.Iterables;
import io.grpc.*;
import io.grpc.health.v1.HealthCheckResponse.ServingStatus;
import io.grpc.protobuf.services.*;
import io.grpc.stub.StreamObserver;
import io.opentelemetry.api.GlobalOpenTelemetry;
import io.opentelemetry.api.OpenTelemetry;
import io.opentelemetry.api.baggage.Baggage;
import io.opentelemetry.api.common.AttributeKey;
import io.opentelemetry.api.common.Attributes;
import io.opentelemetry.api.metrics.LongCounter;
import io.opentelemetry.api.metrics.Meter;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.StatusCode;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.context.Context;
import io.opentelemetry.context.Scope;
import io.opentelemetry.instrumentation.annotations.SpanAttribute;
import io.opentelemetry.instrumentation.annotations.WithSpan;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Optional;
import java.util.Random;
import org.apache.logging.log4j.Level;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import oteldemo.Demo.Ad;
import oteldemo.Demo.AdRequest;
import oteldemo.Demo.AdResponse;
import oteldemo.problempattern.CPULoad;
import dev.openfeature.contrib.providers.flagd.FlagdOptions;
import dev.openfeature.contrib.providers.flagd.FlagdProvider;
import dev.openfeature.sdk.Client;
import dev.openfeature.sdk.EvaluationContext;
import dev.openfeature.sdk.MutableContext;
import dev.openfeature.sdk.OpenFeatureAPI;
import java.util.UUID;


public final class AdService {

  private static final Logger logger = LogManager.getLogger(AdService.class);

  @SuppressWarnings("FieldCanBeLocal")
  private static final int MAX_ADS_TO_SERVE = 2;

  private Server server;
  private HealthStatusManager healthMgr;

  private static final AdService service = new AdService();
  private static final Tracer tracer = GlobalOpenTelemetry.getTracer("ad");
  private static final Meter meter = GlobalOpenTelemetry.getMeter("ad");

  private static final LongCounter adRequestsCounter =
      meter
          .counterBuilder("app.ads.ad_requests")
          .setDescription("Counts ad requests by request and response type")
          .build();

  private static final AttributeKey<String> adRequestTypeKey =
      AttributeKey.stringKey("app.ads.ad_request_type");
  private static final AttributeKey<String> adResponseTypeKey =
      AttributeKey.stringKey("app.ads.ad_response_type");

  private void start() throws IOException {
    int port =
        Integer.parseInt(
            Optional.ofNullable(System.getenv("AD_PORT"))
                .orElseThrow(
                    () ->
                        new IllegalStateException(
                            "environment vars: AD_PORT must not be null")));
    healthMgr = new HealthStatusManager();

    // Create a flagd instance with OpenTelemetry
    FlagdOptions options =
        FlagdOptions.builder()
            .withGlobalTelemetry(true)
            .build();

    FlagdProvider flagdProvider = new FlagdProvider(options);
    // Set flagd as the OpenFeature Provider
    OpenFeatureAPI.getInstance().setProvider(flagdProvider);
  
    server =
        ServerBuilder.forPort(port)
            .addService(new AdServiceImpl())
            .addService(healthMgr.getHealthService())
            .build()
            .start();
    logger.info("Ad service started, listening on " + port);
    Runtime.getRuntime()
        .addShutdownHook(
            new Thread(
                () -> {
                  // Use stderr here since the logger may have been reset by its JVM shutdown hook.
                  System.err.println(
                      "*** shutting down gRPC ads server since JVM is shutting down");
                  AdService.this.stop();
                  System.err.println("*** server shut down");
                }));
    healthMgr.setStatus("", ServingStatus.SERVING);
  }

  private void stop() {
    if (server != null) {
      healthMgr.clearStatus("");
      server.shutdown();
    }
  }

  private enum AdRequestType {
    TARGETED,
    NOT_TARGETED
  }

  private enum AdResponseType {
    TARGETED,
    RANDOM
  }

  private static class AdServiceImpl extends oteldemo.AdServiceGrpc.AdServiceImplBase {
    
    private static final String AD_FAILURE = "adFailure";
    private static final String AD_HIGH_CPU_FEATURE_FLAG = "adHighCpu";
    private static final Client ffClient = OpenFeatureAPI.getInstance().getClient();
    
    private AdServiceImpl() {}

    /**
     * Retrieves ads based on context provided in the request {@code AdRequest}.
     *
     * @param req the request containing context.
     * @param responseObserver the stream observer which gets notified with the value of {@code
     *     AdResponse}
     */
    @Override
    public void getAds(AdRequest req, StreamObserver<AdResponse> responseObserver) {
      AdService service = AdService.getInstance();

      // get the current span in context
      Span span = Span.current();
      try {
        List<Ad> allAds = new ArrayList<>();
        AdRequestType adRequestType;
        AdResponseType adResponseType;

        Baggage baggage = Baggage.fromContextOrNull(Context.current());
        MutableContext evaluationContext = new MutableContext();
        if (baggage != null) {
          final String sessionId = baggage.getEntryValue("session.id");
          span.setAttribute("session.id", sessionId);
          evaluationContext.setTargetingKey(sessionId);
          evaluationContext.add("session", sessionId);
        } else {
          logger.info("no baggage found in context");
        }

        CPULoad cpuload = CPULoad.getInstance();
        cpuload.execute(ffClient.getBooleanValue(AD_HIGH_CPU_FEATURE_FLAG, false, evaluationContext));

        span.setAttribute("app.ads.contextKeys", req.getContextKeysList().toString());
        span.setAttribute("app.ads.contextKeys.count", req.getContextKeysCount());
        if (req.getContextKeysCount() > 0) {
          logger.info("Targeted ad request received for " + req.getContextKeysList());
          for (int i = 0; i < req.getContextKeysCount(); i++) {
            Collection<Ad> ads = service.getAdsByCategory(req.getContextKeys(i));
            allAds.addAll(ads);
          }
          adRequestType = AdRequestType.TARGETED;
          adResponseType = AdResponseType.TARGETED;
        } else {
          logger.info("Non-targeted ad request received, preparing random response.");
          allAds = service.getRandomAds();
          adRequestType = AdRequestType.NOT_TARGETED;
          adResponseType = AdResponseType.RANDOM;
        }
        if (allAds.isEmpty()) {
          // Serve random ads.
          allAds = service.getRandomAds();
          adResponseType = AdResponseType.RANDOM;
        }
        span.setAttribute("app.ads.count", allAds.size());
        span.setAttribute("app.ads.ad_request_type", adRequestType.name());
        span.setAttribute("app.ads.ad_response_type", adResponseType.name());

        adRequestsCounter.add(
            1,
            Attributes.of(
                adRequestTypeKey, adRequestType.name(), adResponseTypeKey, adResponseType.name()));

        // Throw 1/10 of the time to simulate a failure when the feature flag is enabled
        if (ffClient.getBooleanValue(AD_FAILURE, false, evaluationContext) && random.nextInt(10) == 0) {
          throw new StatusRuntimeException(Status.UNAVAILABLE);
        }


        AdResponse reply = AdResponse.newBuilder().addAllAds(allAds).build();
        responseObserver.onNext(reply);
        responseObserver.onCompleted();
      } catch (StatusRuntimeException e) {
        span.addEvent(
            "Error", Attributes.of(AttributeKey.stringKey("exception.message"), e.getMessage()));
        span.setStatus(StatusCode.ERROR);
        logger.log(Level.WARN, "GetAds Failed with status {}", e.getStatus());
        responseObserver.onError(e);
      }
    }
  }

  private static final ImmutableListMultimap<String, Ad> adsMap = createAdsMap();

  @WithSpan("getAdsByCategory")
  private Collection<Ad> getAdsByCategory(@SpanAttribute("app.ads.category") String category) {
    Collection<Ad> ads = adsMap.get(category);
    Span.current().setAttribute("app.ads.count", ads.size());
    return ads;
  }

  private static final Random random = new Random();

  private List<Ad> getRandomAds() {

    List<Ad> ads = new ArrayList<>(MAX_ADS_TO_SERVE);

    // create and start a new span manually
    Span span = tracer.spanBuilder("getRandomAds").startSpan();

    // put the span into context, so if any child span is started the parent will be set properly
    try (Scope ignored = span.makeCurrent()) {

      Collection<Ad> allAds = adsMap.values();
      for (int i = 0; i < MAX_ADS_TO_SERVE; i++) {
        ads.add(Iterables.get(allAds, random.nextInt(allAds.size())));
      }
      span.setAttribute("app.ads.count", ads.size());

    } finally {
      span.end();
    }

    return ads;
  }

  private static AdService getInstance() {
    return service;
  }

  /** Await termination on the main thread since the grpc library uses daemon threads. */
  private void blockUntilShutdown() throws InterruptedException {
    if (server != null) {
      server.awaitTermination();
    }
  }

  private static ImmutableListMultimap<String, Ad> createAdsMap() {
    Ad binoculars =
        Ad.newBuilder()
            .setRedirectUrl("/product/2ZYFJ3GM2N")
            .setText("Roof Binoculars for sale. 50% off.")
            .build();
    Ad explorerTelescope =
        Ad.newBuilder()
            .setRedirectUrl("/product/66VCHSJNUP")
            .setText("Starsense Explorer Refractor Telescope for sale. 20% off.")
            .build();
    Ad colorImager =
        Ad.newBuilder()
            .setRedirectUrl("/product/0PUK6V6EV0")
            .setText("Solar System Color Imager for sale. 30% off.")
            .build();
    Ad opticalTube =
        Ad.newBuilder()
            .setRedirectUrl("/product/9SIQT8TOJO")
            .setText("Optical Tube Assembly for sale. 10% off.")
            .build();
    Ad travelTelescope =
        Ad.newBuilder()
            .setRedirectUrl("/product/1YMWWN1N4O")
            .setText(
                "Eclipsmart Travel Refractor Telescope for sale. Buy one, get second kit for free")
            .build();
    Ad solarFilter =
        Ad.newBuilder()
            .setRedirectUrl("/product/6E92ZMYYFZ")
            .setText("Solar Filter for sale. Buy two, get third one for free")
            .build();
    Ad cleaningKit =
        Ad.newBuilder()
            .setRedirectUrl("/product/L9ECAV7KIM")
            .setText("Lens Cleaning Kit for sale. Buy one, get second one for free")
            .build();
    return ImmutableListMultimap.<String, Ad>builder()
        .putAll("binoculars", binoculars)
        .putAll("telescopes", explorerTelescope)
        .putAll("accessories", colorImager, solarFilter, cleaningKit)
        .putAll("assembly", opticalTube)
        .putAll("travel", travelTelescope)
        // Keep the books category free of ads to ensure the random code branch is tested
        .build();
  }

  /** Main launches the server from the command line. */
  public static void main(String[] args) throws IOException, InterruptedException {
    // Start the RPC server. You shouldn't see any output from gRPC before this.
    logger.info("Ad service starting.");
    final AdService service = AdService.getInstance();
    service.start();
    service.blockUntilShutdown();
  }
}
