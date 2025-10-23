// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

package com.opentelemetry.demo.shopdcshim.service;

import com.opentelemetry.demo.shopdcshim.dto.ShopPurchaseRequest;
import com.opentelemetry.demo.shopdcshim.entity.ShopTransaction;
import com.opentelemetry.demo.shopdcshim.repository.ShopTransactionRepository;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.Tracer;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Async;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;

@Service
@RequiredArgsConstructor
@Slf4j
public class ShopTransactionService {

    private final ShopTransactionRepository transactionRepository;
    private final CloudCheckoutService cloudCheckoutService;
    private final Tracer tracer;
    private final ObjectMapper objectMapper;

    @Transactional
    public String initiateShopPurchase(ShopPurchaseRequest request) {
        Span span = tracer.spanBuilder("initiate_shop_purchase")
                .setAttribute("shop.store.location", request.getStoreLocation())
                .setAttribute("shop.terminal.id", request.getTerminalId())
                .setAttribute("shop.customer.email", request.getCustomerEmail())
                .setAttribute("shop.total.amount", request.getTotalAmount().doubleValue())
                .setAttribute("shop.currency", request.getCurrencyCode())
                .startSpan();

        try {
            // Generate transaction ID and local order ID
            String transactionId = UUID.randomUUID().toString();
            String localOrderId = generateLocalOrderId(request.getStoreLocation(), request.getTerminalId());

            log.info("Initiating shop purchase - Transaction ID: {}, Local Order: {}, Store: {}, Terminal: {}", 
                    transactionId, localOrderId, request.getStoreLocation(), request.getTerminalId());

            // Create local transaction record
            ShopTransaction transaction = new ShopTransaction();
            transaction.setTransactionId(transactionId);
            transaction.setLocalOrderId(localOrderId);
            transaction.setCustomerEmail(request.getCustomerEmail());
            transaction.setCustomerName(request.getCustomerName());
            transaction.setTotalAmount(request.getTotalAmount());
            transaction.setCurrencyCode(request.getCurrencyCode());
            transaction.setStoreLocation(request.getStoreLocation());
            transaction.setTerminalId(request.getTerminalId());
            transaction.setStatus(ShopTransaction.TransactionStatus.INITIATED);
            
            // Serialize complex data as JSON
            try {
                transaction.setShippingAddress(objectMapper.writeValueAsString(request.getShippingAddress()));
                transaction.setItemsJson(objectMapper.writeValueAsString(request.getItems()));
            } catch (JsonProcessingException e) {
                log.error("Error serializing transaction data for {}", transactionId, e);
                throw new RuntimeException("Failed to process transaction data", e);
            }

            transactionRepository.save(transaction);

            span.setAttribute("shop.transaction.id", transactionId);
            span.setAttribute("shop.local.order.id", localOrderId);

            // Process asynchronously
            processTransactionAsync(transactionId, request);

            log.info("Shop purchase initiated successfully - Transaction ID: {}", transactionId);
            return transactionId;

        } catch (Exception e) {
            span.recordException(e);
            log.error("Failed to initiate shop purchase for store {} terminal {}", 
                    request.getStoreLocation(), request.getTerminalId(), e);
            throw e;
        } finally {
            span.end();
        }
    }

    @Async
    @Transactional
    public CompletableFuture<Void> processTransactionAsync(String transactionId, ShopPurchaseRequest request) {
        Span span = tracer.spanBuilder("process_shop_transaction")
                .setAttribute("shop.transaction.id", transactionId)
                .startSpan();

        try {
            ShopTransaction transaction = transactionRepository.findByTransactionId(transactionId)
                    .orElseThrow(() -> new RuntimeException("Transaction not found: " + transactionId));

            log.info("Processing transaction {} in background", transactionId);

            // Step 1: Validation
            transaction.setStatus(ShopTransaction.TransactionStatus.VALIDATING);
            transactionRepository.save(transaction);

            // Simulate local validation (inventory check, fraud detection, etc.)
            performLocalValidation(transaction, request);

            // Step 2: Submit to cloud
            transaction.setStatus(ShopTransaction.TransactionStatus.SUBMITTING_CLOUD);
            transaction.setCloudSubmittedAt(LocalDateTime.now());
            transactionRepository.save(transaction);

            CloudCheckoutService.CloudCheckoutResult cloudResult = 
                    cloudCheckoutService.submitToCloudCheckout(transaction.getLocalOrderId(), request);

            // Step 3: Process cloud response
            if (cloudResult.isSuccess()) {
                transaction.setStatus(ShopTransaction.TransactionStatus.COMPLETED);
                transaction.setCloudOrderId(cloudResult.getCloudOrderId());
                transaction.setCloudConfirmedAt(LocalDateTime.now());
                transaction.setProcessedAt(LocalDateTime.now());
                
                span.setAttribute("shop.cloud.order.id", cloudResult.getCloudOrderId());
                span.setAttribute("shop.success", true);
                
                log.info("Transaction {} completed successfully - Cloud Order: {}", 
                        transactionId, cloudResult.getCloudOrderId());
            } else {
                transaction.setStatus(ShopTransaction.TransactionStatus.FAILED);
                transaction.setErrorMessage(cloudResult.getErrorMessage());
                transaction.setProcessedAt(LocalDateTime.now());
                
                span.setAttribute("shop.success", false);
                span.setAttribute("error.message", cloudResult.getErrorMessage());
                
                log.error("Transaction {} failed - Error: {}", transactionId, cloudResult.getErrorMessage());
            }

            transactionRepository.save(transaction);
            return CompletableFuture.completedFuture(null);

        } catch (Exception e) {
            span.recordException(e);
            log.error("Error processing transaction {}", transactionId, e);
            
            // Update transaction with error
            transactionRepository.findByTransactionId(transactionId).ifPresent(t -> {
                t.setStatus(ShopTransaction.TransactionStatus.FAILED);
                t.setErrorMessage("Processing error: " + e.getMessage());
                t.setProcessedAt(LocalDateTime.now());
                transactionRepository.save(t);
            });
            
            return CompletableFuture.failedFuture(e);
        } finally {
            span.end();
        }
    }

    private void performLocalValidation(ShopTransaction transaction, ShopPurchaseRequest request) {
        // Simulate on-premises validation logic
        // - Check local inventory
        // - Validate customer information
        // - Perform fraud detection
        // - Check payment limits
        
        try {
            Thread.sleep(100); // Simulate processing time
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
        
        log.info("Local validation completed for transaction {}", transaction.getTransactionId());
    }

    private String generateLocalOrderId(String storeLocation, String terminalId) {
        String timestamp = String.valueOf(System.currentTimeMillis());
        String storeCode = storeLocation.replaceAll("[^A-Z0-9]", "").substring(0, 
                Math.min(3, storeLocation.length()));
        String terminalCode = terminalId.replaceAll("[^A-Z0-9]", "");
        
        return String.format("DC-%s-%s-%s", storeCode, terminalCode, timestamp.substring(timestamp.length() - 6));
    }

    @Transactional(readOnly = true)
    public ShopTransaction getTransactionStatus(String transactionId) {
        return transactionRepository.findByTransactionId(transactionId)
                .orElseThrow(() -> new RuntimeException("Transaction not found: " + transactionId));
    }

    @Transactional(readOnly = true)
    public List<ShopTransaction> getTransactionsByStore(String storeLocation, LocalDateTime since) {
        return transactionRepository.findByStoreLocationAndCreatedAtAfter(storeLocation, since);
    }

    @Scheduled(fixedRate = 60000) // Run every minute
    @Transactional
    public void processStaleTransactions() {
        Span span = tracer.spanBuilder("process_stale_transactions").startSpan();
        
        try {
            LocalDateTime cutoffTime = LocalDateTime.now().minusMinutes(10);
            
            List<ShopTransaction> staleSubmitting = transactionRepository
                    .findStaleTransactionsByStatus(ShopTransaction.TransactionStatus.SUBMITTING_CLOUD, cutoffTime);
            
            List<ShopTransaction> staleValidating = transactionRepository
                    .findStaleTransactionsByStatus(ShopTransaction.TransactionStatus.VALIDATING, cutoffTime);

            int processed = 0;
            
            for (ShopTransaction transaction : staleSubmitting) {
                log.warn("Found stale transaction {} in SUBMITTING_CLOUD state, marking as failed", 
                        transaction.getTransactionId());
                transaction.setStatus(ShopTransaction.TransactionStatus.FAILED);
                transaction.setErrorMessage("Transaction timeout - cloud submission stalled");
                transaction.setProcessedAt(LocalDateTime.now());
                transactionRepository.save(transaction);
                processed++;
            }
            
            for (ShopTransaction transaction : staleValidating) {
                log.warn("Found stale transaction {} in VALIDATING state, marking as failed", 
                        transaction.getTransactionId());
                transaction.setStatus(ShopTransaction.TransactionStatus.FAILED);
                transaction.setErrorMessage("Transaction timeout - validation stalled");
                transaction.setProcessedAt(LocalDateTime.now());
                transactionRepository.save(transaction);
                processed++;
            }

            span.setAttribute("stale_transactions_processed", processed);
            
            if (processed > 0) {
                log.info("Processed {} stale transactions", processed);
            }

        } catch (Exception e) {
            span.recordException(e);
            log.error("Error processing stale transactions", e);
        } finally {
            span.end();
        }
    }

    @Transactional(readOnly = true)
    public TransactionStats getTransactionStats() {
        long initiated = transactionRepository.countByStatus(ShopTransaction.TransactionStatus.INITIATED);
        long validating = transactionRepository.countByStatus(ShopTransaction.TransactionStatus.VALIDATING);
        long submittingCloud = transactionRepository.countByStatus(ShopTransaction.TransactionStatus.SUBMITTING_CLOUD);
        long completed = transactionRepository.countByStatus(ShopTransaction.TransactionStatus.COMPLETED);
        long failed = transactionRepository.countByStatus(ShopTransaction.TransactionStatus.FAILED);
        
        LocalDateTime oneHourAgo = LocalDateTime.now().minusHours(1);
        long completedLastHour = transactionRepository.countCompletedTransactionsSince(oneHourAgo);
        
        Double avgProcessingTime = transactionRepository.getAverageProcessingTimeSeconds(oneHourAgo);
        
        return new TransactionStats(initiated, validating, submittingCloud, completed, failed, 
                completedLastHour, avgProcessingTime != null ? avgProcessingTime : 0.0);
    }

    public static class TransactionStats {
        private final long initiated;
        private final long validating;
        private final long submittingCloud;
        private final long completed;
        private final long failed;
        private final long completedLastHour;
        private final double avgProcessingTimeSeconds;

        public TransactionStats(long initiated, long validating, long submittingCloud, 
                               long completed, long failed, long completedLastHour, 
                               double avgProcessingTimeSeconds) {
            this.initiated = initiated;
            this.validating = validating;
            this.submittingCloud = submittingCloud;
            this.completed = completed;
            this.failed = failed;
            this.completedLastHour = completedLastHour;
            this.avgProcessingTimeSeconds = avgProcessingTimeSeconds;
        }

        // Getters
        public long getInitiated() { return initiated; }
        public long getValidating() { return validating; }
        public long getSubmittingCloud() { return submittingCloud; }
        public long getCompleted() { return completed; }
        public long getFailed() { return failed; }
        public long getCompletedLastHour() { return completedLastHour; }
        public double getAvgProcessingTimeSeconds() { return avgProcessingTimeSeconds; }
    }
}
