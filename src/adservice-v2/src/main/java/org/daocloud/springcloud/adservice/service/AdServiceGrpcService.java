package org.daocloud.springcloud.adservice.service;

import com.google.common.collect.ImmutableListMultimap;
import com.google.common.collect.Iterables;
import com.google.protobuf.Descriptors;
import hipstershop.AdServiceGrpc;
import hipstershop.Demo.Ad;
import hipstershop.Demo.AdRequest;
import hipstershop.Demo.AdResponse;
import io.grpc.StatusRuntimeException;
import io.grpc.Status;
import io.grpc.stub.StreamObserver;
import io.opentelemetry.api.GlobalOpenTelemetry;
import io.opentelemetry.api.common.AttributeKey;
import io.opentelemetry.api.common.Attributes;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.StatusCode;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.context.Scope;
import io.opentelemetry.extension.annotations.WithSpan;
import net.devh.boot.grpc.server.service.GrpcService;
import org.apache.logging.log4j.Level;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.daocloud.springcloud.adservice.Interceptor.MeterInterceptor;
import org.daocloud.springcloud.adservice.meter.Meter;
import org.ejml.simple.SimpleMatrix;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;

import java.util.*;

@GrpcService
public class AdServiceGrpcService extends AdServiceGrpc.AdServiceImplBase {

    private static final Logger logger = LogManager.getLogger(AdServiceGrpcService.class);
    private final ImmutableListMultimap<String, Ad> adsMap = createAdsMap();

    @Autowired
    private Meter meterProvider;

    @Value("${spring.extraAdLabel}")
    private String text;

    @Value("${spring.randomError}")
    private boolean randomError;

    @Value("${spring.matrixRow}")
    private int matrixRow;

    @Override
    public void getAds(AdRequest req, StreamObserver<AdResponse> responseObserver) {
        // get the current span in context
        Span span = Span.current();
        try{
            List<Ad> allAds = new ArrayList<>();

            span.setAttribute("app.ads.contextKeys", req.getContextKeysList().toString());
            span.setAttribute("app.ads.contextKeys.count", req.getContextKeysCount());
            logger.info("received ad request (context_words=" + req.getContextKeysList() + ")");

            // do matrixCalculate
            matrixCalculate(matrixRow);

            if(randomError){
                //throw random error
                Random random = new Random();
                int r = random.nextInt(100)+1;
                if(r > 50){
                    throw new StatusRuntimeException(Status.INTERNAL.withDescription("connect Canceled randomly"));
                }
            }

            if (req.getContextKeysCount() > 0) {
                for (int i = 0; i < req.getContextKeysCount(); i++) {
                    Collection<Ad> ads = getAdsByCategory(req.getContextKeys(i));
                    allAds.addAll(ads);
                }
            } else {
                allAds = getRandomAds();
            }
            if (allAds.isEmpty()) {
                // Serve random ads.
                allAds = getRandomAds();
            }

            List<Ad>  allAdsLabeled = addLabel(allAds);

            span.setAttribute("app.ads.count", allAdsLabeled.size());
            AdResponse reply = AdResponse.newBuilder().addAllAds(allAdsLabeled).build();
            responseObserver.onNext(reply);
            responseObserver.onCompleted();
        } catch (StatusRuntimeException e) {
            Attributes attributes = Attributes.of(AttributeKey.stringKey("operation"),(String) MeterInterceptor.operation.get(),
                    AttributeKey.stringKey("failed"),"true");
            meterProvider.getGrpcCalls().add(1,attributes);
            span.addEvent(
                    "Error", Attributes.of(AttributeKey.stringKey("exception.message"), e.getMessage()));
            span.setStatus(StatusCode.ERROR);
            logger.log(Level.WARN, "GetAds Failed with status {}", e.getStatus());
            responseObserver.onError(e);
        }
    }

    @WithSpan("getAdsByCategory")
    private Collection<Ad> getAdsByCategory(String category) {
        Collection<Ad> ads = adsMap.get(category);
        Span.current().setAttribute("app.ads.count", ads.size());
        return ads;
    }

    private static final Random random = new Random();
    private static final int MAX_ADS_TO_SERVE = 2;
    private List<Ad> getRandomAds() {
        List<Ad> ads = new ArrayList<>(MAX_ADS_TO_SERVE);

        // create and start a new span manually
        Tracer tracer = GlobalOpenTelemetry.getTracer("adservice");
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
    private ImmutableListMultimap<String, Ad> createAdsMap() {
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
                        .setText("Eclipsmart Travel Refractor Telescope for sale. Buy one, get second kit for free")
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
                .build();
    }

    private List<Ad> addLabel(List<Ad> allAds){
        List<Ad> allAdsLabeled = new ArrayList<>();

        for(Ad old:allAds){
            Ad labeledAd = Ad.newBuilder()
                    .setRedirectUrl(old.getRedirectUrl())
                    .setText(old.getText()+" -- "+text)
                    .build();
            allAdsLabeled.add(labeledAd);
        }
        return allAdsLabeled;
    }

    private long matrixCalculate(int row){
        long start = System.currentTimeMillis();

        SimpleMatrix matrixD = new SimpleMatrix(row, row);
        Random random = new Random();
        for (int i = 0; i < row; i++) {
            for (int j = 0; j < row; j++) {
                int var = random.nextInt(1000);
                if (i == j) {
                    matrixD.set(i, j, var);
                } else {
                    matrixD.set(i, j, var);
                }
            }
        }
        matrixD.transpose();
        matrixD.normF();
        matrixD.invert();
        matrixD.pseudoInverse();

        long finish = System.currentTimeMillis();
        long timeElapsed = finish - start;
        logger.info(new Formatter().format("exec %dx%d matrix calculation, spend: %s ms",row,row,timeElapsed));
        return timeElapsed;
    }
}
