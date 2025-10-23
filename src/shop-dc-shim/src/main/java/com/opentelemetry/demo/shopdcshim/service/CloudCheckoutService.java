// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

package com.opentelemetry.demo.shopdcshim.service;

import com.opentelemetry.demo.shopdcshim.dto.ShopPurchaseRequest;
import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.Tracer;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import oteldemo.Demo.*;
import oteldemo.CheckoutServiceGrpc;

import javax.annotation.PreDestroy;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

@Service
@Slf4j
public class CloudCheckoutService {

    private final ManagedChannel channel;
    private final CheckoutServiceGrpc.CheckoutServiceBlockingStub checkoutStub;
    private final Tracer tracer;
    private final String checkoutServiceAddr;

    public CloudCheckoutService(
            @Value("${app.cloud.checkout.addr:checkout:8080}") String checkoutServiceAddr,
            Tracer tracer) {
        this.checkoutServiceAddr = checkoutServiceAddr;
        this.tracer = tracer;
        
        // Create gRPC channel
        this.channel = ManagedChannelBuilder.forTarget(checkoutServiceAddr)
                .usePlaintext()
                .build();
        
        this.checkoutStub = CheckoutServiceGrpc.newBlockingStub(channel);
        
        log.info("Initialized Cloud Checkout Service with gRPC address: {}", checkoutServiceAddr);
    }
    
    @PreDestroy
    public void shutdown() {
        if (channel != null && !channel.isShutdown()) {
            try {
                channel.shutdown().awaitTermination(5, TimeUnit.SECONDS);
            } catch (InterruptedException e) {
                log.warn("Failed to shutdown gRPC channel gracefully", e);
                Thread.currentThread().interrupt();
            }
        }
    }

    public CloudCheckoutResult submitToCloudCheckout(String localOrderId, ShopPurchaseRequest request) {
        Span span = tracer.spanBuilder("cloud_checkout_call")
                .setAttribute("local.order.id", localOrderId)
                .setAttribute("cloud.service", "checkout")
                .setAttribute("checkout.customer.email", request.getCustomerEmail())
                .setAttribute("checkout.store.location", request.getStoreLocation())
                .setAttribute("checkout.terminal.id", request.getTerminalId())
                .setAttribute("rpc.system", "grpc")
                .setAttribute("rpc.service", "oteldemo.CheckoutService")
                .setAttribute("rpc.method", "PlaceOrder")
                .startSpan();

        try {
            log.info("Submitting order {} via gRPC to checkout service for customer {}", 
                    localOrderId, request.getCustomerEmail());

            // Generate a unique user ID for this transaction  
            String userId = "shop-dc-" + UUID.randomUUID().toString();

            // Build the gRPC PlaceOrderRequest
            PlaceOrderRequest grpcRequest = buildGrpcRequest(userId, request);

            // Make the gRPC call to checkout service
            PlaceOrderResponse response = checkoutStub.placeOrder(grpcRequest);
            
            String cloudOrderId = response.getOrder().getOrderId();
            String trackingId = response.getOrder().getShippingTrackingId();
            
            span.setAttribute("cloud.checkout.success", true);
            span.setAttribute("cloud.order.id", cloudOrderId);
            span.setAttribute("cloud.user.id", userId);
            
            log.info("Cloud checkout successful for local order {}, cloud order ID: {}", 
                    localOrderId, cloudOrderId);
            
            return new CloudCheckoutResult(true, cloudOrderId, trackingId, null);

        } catch (Exception e) {
            span.recordException(e);
            span.setAttribute("cloud.checkout.success", false);
            
            log.error("gRPC call to checkout failed for local order {}: {}", localOrderId, e.getMessage());
            
            return new CloudCheckoutResult(false, null, null, "gRPC error: " + e.getMessage());
        } finally {
            span.end();
        }
    }

    
    private PlaceOrderRequest buildGrpcRequest(String userId, ShopPurchaseRequest request) {
        // Build Address protobuf
        Address address = Address.newBuilder()
                .setStreetAddress(request.getShippingAddress().getStreetAddress())
                .setCity(request.getShippingAddress().getCity())
                .setState(request.getShippingAddress().getState())
                .setCountry(request.getShippingAddress().getCountry())
                .setZipCode(request.getShippingAddress().getZipCode())
                .build();
        
        // Build CreditCardInfo protobuf
        CreditCardInfo creditCard = CreditCardInfo.newBuilder()
                .setCreditCardNumber(request.getCreditCard().getCreditCardNumber())
                .setCreditCardCvv(request.getCreditCard().getCreditCardCvv())
                .setCreditCardExpirationMonth(request.getCreditCard().getExpirationMonth())
                .setCreditCardExpirationYear(request.getCreditCard().getExpirationYear())
                .build();
        
        // Build PlaceOrderRequest protobuf
        return PlaceOrderRequest.newBuilder()
                .setUserId(userId)
                .setUserCurrency(request.getCurrencyCode())
                .setEmail(request.getCustomerEmail())
                .setAddress(address)
                .setCreditCard(creditCard)
                .build();
    }


    public static class CloudCheckoutResult {
        private final boolean success;
        private final String cloudOrderId;
        private final String trackingId;
        private final String errorMessage;

        public CloudCheckoutResult(boolean success, String cloudOrderId, String trackingId, String errorMessage) {
            this.success = success;
            this.cloudOrderId = cloudOrderId;
            this.trackingId = trackingId;
            this.errorMessage = errorMessage;
        }

        public boolean isSuccess() { return success; }
        public String getCloudOrderId() { return cloudOrderId; }
        public String getTrackingId() { return trackingId; }
        public String getErrorMessage() { return errorMessage; }
    }
}