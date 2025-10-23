// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

package com.opentelemetry.demo.shopdcshim.controller;

import com.opentelemetry.demo.shopdcshim.dto.ShopPurchaseRequest;
import com.opentelemetry.demo.shopdcshim.entity.ShopTransaction;
import com.opentelemetry.demo.shopdcshim.service.ShopTransactionService;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.Tracer;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/shop")
@RequiredArgsConstructor
@Slf4j
public class ShopController {

    private final ShopTransactionService transactionService;
    private final Tracer tracer;

    @PostMapping("/purchase")
    public ResponseEntity<Map<String, Object>> processPurchase(@Valid @RequestBody ShopPurchaseRequest request) {
        Span span = tracer.spanBuilder("shop_api_purchase")
                .setAttribute("http.method", "POST")
                .setAttribute("http.route", "/api/shop/purchase")
                .setAttribute("shop.store.location", request.getStoreLocation())
                .setAttribute("shop.terminal.id", request.getTerminalId())
                .startSpan();

        try {
            log.info("Received shop purchase request from store: {}, terminal: {}, customer: {}", 
                    request.getStoreLocation(), request.getTerminalId(), request.getCustomerEmail());

            String transactionId = transactionService.initiateShopPurchase(request);

            span.setAttribute("shop.transaction.id", transactionId);
            span.setAttribute("http.status_code", 202);

            return ResponseEntity.accepted()
                    .body(Map.of(
                            "transactionId", transactionId,
                            "status", "accepted",
                            "message", "Purchase request received and is being processed",
                            "storeLocation", request.getStoreLocation(),
                            "terminalId", request.getTerminalId()
                    ));

        } catch (Exception e) {
            span.recordException(e);
            span.setAttribute("http.status_code", 500);
            log.error("Error processing purchase request from store {} terminal {}", 
                    request.getStoreLocation(), request.getTerminalId(), e);

            return ResponseEntity.internalServerError()
                    .body(Map.of(
                            "error", "Internal server error",
                            "message", e.getMessage(),
                            "storeLocation", request.getStoreLocation(),
                            "terminalId", request.getTerminalId()
                    ));
        } finally {
            span.end();
        }
    }

    @GetMapping("/transaction/{transactionId}")
    public ResponseEntity<Map<String, Object>> getTransactionStatus(@PathVariable String transactionId) {
        Span span = tracer.spanBuilder("shop_api_transaction_status")
                .setAttribute("http.method", "GET")
                .setAttribute("http.route", "/api/shop/transaction/{transactionId}")
                .setAttribute("shop.transaction.id", transactionId)
                .startSpan();

        try {
            ShopTransaction transaction = transactionService.getTransactionStatus(transactionId);

            span.setAttribute("shop.transaction.status", transaction.getStatus().toString());
            span.setAttribute("shop.store.location", transaction.getStoreLocation());
            span.setAttribute("http.status_code", 200);

            Map<String, Object> response = new HashMap<>();
            response.put("transactionId", transaction.getTransactionId());
            response.put("localOrderId", transaction.getLocalOrderId());
            response.put("cloudOrderId", transaction.getCloudOrderId() != null ? transaction.getCloudOrderId() : "");
            response.put("status", transaction.getStatus());
            response.put("customerEmail", transaction.getCustomerEmail());
            response.put("customerName", transaction.getCustomerName());
            response.put("totalAmount", transaction.getTotalAmount());
            response.put("currencyCode", transaction.getCurrencyCode());
            response.put("storeLocation", transaction.getStoreLocation());
            response.put("terminalId", transaction.getTerminalId());
            response.put("createdAt", transaction.getCreatedAt());
            response.put("processedAt", transaction.getProcessedAt());
            response.put("cloudSubmittedAt", transaction.getCloudSubmittedAt());
            response.put("cloudConfirmedAt", transaction.getCloudConfirmedAt());
            response.put("errorMessage", transaction.getErrorMessage() != null ? transaction.getErrorMessage() : "");

            return ResponseEntity.ok(response);

        } catch (RuntimeException e) {
            span.setAttribute("http.status_code", 404);
            log.warn("Transaction not found: {}", transactionId);

            return ResponseEntity.notFound().build();

        } catch (Exception e) {
            span.recordException(e);
            span.setAttribute("http.status_code", 500);
            log.error("Error retrieving transaction status: {}", transactionId, e);

            return ResponseEntity.internalServerError()
                    .body(Map.of(
                            "error", "Internal server error",
                            "message", e.getMessage()
                    ));
        } finally {
            span.end();
        }
    }

    @GetMapping("/store/{storeLocation}/transactions")
    public ResponseEntity<Map<String, Object>> getStoreTransactions(
            @PathVariable String storeLocation,
            @RequestParam(defaultValue = "24") int hours) {
        
        Span span = tracer.spanBuilder("shop_api_store_transactions")
                .setAttribute("http.method", "GET")
                .setAttribute("http.route", "/api/shop/store/{storeLocation}/transactions")
                .setAttribute("shop.store.location", storeLocation)
                .startSpan();

        try {
            LocalDateTime since = LocalDateTime.now().minusHours(hours);
            List<ShopTransaction> transactions = transactionService.getTransactionsByStore(storeLocation, since);

            span.setAttribute("shop.transactions.count", transactions.size());
            span.setAttribute("http.status_code", 200);

            return ResponseEntity.ok(Map.of(
                    "storeLocation", storeLocation,
                    "hoursBack", hours,
                    "transactionCount", transactions.size(),
                    "transactions", transactions
            ));

        } catch (Exception e) {
            span.recordException(e);
            span.setAttribute("http.status_code", 500);
            log.error("Error retrieving store transactions for {}", storeLocation, e);

            return ResponseEntity.internalServerError()
                    .body(Map.of(
                            "error", "Internal server error", 
                            "message", e.getMessage()
                    ));
        } finally {
            span.end();
        }
    }

    @GetMapping("/health")
    public ResponseEntity<Map<String, Object>> health() {
        ShopTransactionService.TransactionStats stats = transactionService.getTransactionStats();

        return ResponseEntity.ok(Map.of(
                "status", "healthy",
                "service", "shop-dc-shim",
                "environment", "datacenter-b01",
                "description", "On-premises shop datacenter shim service for cloud checkout integration",
                "transactions", Map.of(
                        "initiated", stats.getInitiated(),
                        "validating", stats.getValidating(),
                        "submittingCloud", stats.getSubmittingCloud(),
                        "completed", stats.getCompleted(),
                        "failed", stats.getFailed(),
                        "completedLastHour", stats.getCompletedLastHour(),
                        "avgProcessingTimeSeconds", stats.getAvgProcessingTimeSeconds()
                )
        ));
    }

    @GetMapping("/stats")
    public ResponseEntity<Map<String, Object>> getStats() {
        ShopTransactionService.TransactionStats stats = transactionService.getTransactionStats();

        return ResponseEntity.ok(Map.of(
                "environment", "datacenter-b01",
                "service", "shop-dc-shim",
                "timestamp", LocalDateTime.now(),
                "transactions", Map.of(
                        "initiated", stats.getInitiated(),
                        "validating", stats.getValidating(),
                        "submittingCloud", stats.getSubmittingCloud(),
                        "completed", stats.getCompleted(),
                        "failed", stats.getFailed()
                ),
                "performance", Map.of(
                        "completedLastHour", stats.getCompletedLastHour(),
                        "avgProcessingTimeSeconds", stats.getAvgProcessingTimeSeconds()
                )
        ));
    }
}
