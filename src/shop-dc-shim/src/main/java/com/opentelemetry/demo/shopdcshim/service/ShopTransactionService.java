// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

package com.opentelemetry.demo.shopdcshim.service;

import com.opentelemetry.demo.shopdcshim.dto.ShopPurchaseRequest;
import com.opentelemetry.demo.shopdcshim.entity.ShopTransaction;
import com.opentelemetry.demo.shopdcshim.repository.ShopTransactionRepository;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.zaxxer.hikari.HikariDataSource;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.Tracer;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Async;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import javax.sql.DataSource;

import java.math.BigDecimal;
import java.security.MessageDigest;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
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
    private final DataSource dataSource;

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
            
            // Initial validation processing
            processTransactionData(request, transactionId, 170);
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
            transactionRepository.flush(); // Ensure transaction is visible before async processing

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
        log.info("Starting local validation for transaction {}", transaction.getTransactionId());
        

        processTransactionData(request, transaction.getTransactionId(), 150);
        
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
        performStatusCheckProcessing(transactionId, 550);
        return transactionRepository.findByTransactionId(transactionId)
                .orElseThrow(() -> new RuntimeException("Transaction not found: " + transactionId));
    }

    @Transactional(readOnly = true)
    public List<ShopTransaction> getTransactionsByStore(String storeLocation, LocalDateTime since) {
        return transactionRepository.findByStoreLocationAndCreatedAtAfter(storeLocation, since);
    }

    @Scheduled(fixedRate = 600000) // Run 10 minutes
    @Transactional
    public void processStaleTransactions() {
        Span span = tracer.spanBuilder("process_stale_transactions").startSpan();
        
        try {
            LocalDateTime cutoffTime = LocalDateTime.now().minusMinutes(10);
            
            List<ShopTransaction> staleSubmitting = transactionRepository
                    .findStaleTransactionsByStatus("SUBMITTING_CLOUD", cutoffTime);
            
            List<ShopTransaction> staleValidating = transactionRepository
                    .findStaleTransactionsByStatus("VALIDATING", cutoffTime);

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

    // Were doign this to create a pagelatch contention with inserts 
    // clean them up if theyre older than 1 hour
    @Scheduled(fixedRate = 300000)
    @Transactional
    public void syncComplianceAuditLog() {
        try {
            int recordCount = 29 + new java.util.Random().nextInt(53); // Random between 29 and 53
            log.info("Starting compliance audit sync - spawning {} concurrent write threads", recordCount);
            String[] stores = {"Seattle-WA", "Portland-OR", "Denver-CO", "Austin-TX"};
            List<CompletableFuture<Void>> tasks = new ArrayList<>();
            
            for (int i = 0; i < recordCount; i++) {
                final int idx = i;
                tasks.add(CompletableFuture.runAsync(() -> {
                    ShopTransaction audit = new ShopTransaction();
                    audit.setTransactionId("AUDIT-" + UUID.randomUUID().toString().substring(0, 13));
                    audit.setLocalOrderId("DC-CMPL-" + System.currentTimeMillis());
                    audit.setCustomerEmail("audit.sync+" + idx + "@internal.system");
                    audit.setCustomerName("Audit Sync");
                    audit.setTotalAmount(BigDecimal.valueOf(0.01));
                    audit.setCurrencyCode("USD");
                    audit.setStoreLocation(stores[idx % stores.length]);
                    audit.setTerminalId("REG" + String.format("%03d", idx));
                    audit.setStatus(ShopTransaction.TransactionStatus.COMPLETED);
                    audit.setItemsJson("[]");
                    audit.setShippingAddress("{}");
                    transactionRepository.save(audit);
                }));
            }
            CompletableFuture.allOf(tasks.toArray(new CompletableFuture[0])).join();
            log.info("Compliance audit sync completed - {} records written", recordCount);
        } catch (Exception e) {
            log.warn("Audit sync error: {}", e.getMessage());
        }
    }

    @Scheduled(fixedRate = 600000)
    @Transactional
    public void cleanupOldAuditRecords() {
        try {
            log.debug("Cleaning up audit records older than 1 hour");
            transactionRepository.deleteInternalAuditRecordsOlderThan(LocalDateTime.now().minusHours(1));
        } catch (Exception e) {
            log.warn("Audit cleanup error: {}", e.getMessage());
        }
    }

    @Scheduled(fixedRate = 7200000) // Run every 2 hours
    @Transactional
    public void cleanupOldTransactions() {
        log.info("Starting scheduled cleanup of transactions older than 2 hours");
        Span span = tracer.spanBuilder("cleanup_old_transactions").startSpan();
        
        try {
            LocalDateTime cutoffTime = LocalDateTime.now().minusHours(2);
            int deletedCount = transactionRepository.deleteTransactionsOlderThan(cutoffTime);
            
            span.setAttribute("transactions_deleted", deletedCount);
            
            if (deletedCount > 0) {
                log.info("Cleaned up {} transactions older than 2 hours", deletedCount);
            } else {
                log.info("No transactions to clean up (older than 2 hours)");
            }
        } catch (Exception e) {
            span.recordException(e);
            log.error("Error cleaning up old transactions", e);
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

    private void processTransactionData(ShopPurchaseRequest request, String transactionId, int durationMs) {
        long startTime = System.currentTimeMillis();
        long endTime = startTime + durationMs;
        
        log.info("🔄 Starting processing for transaction {} - target duration: {} ms", transactionId, durationMs);
        
        // Memory-intensive: Allocate large data structures
        List<Map<String, Object>> dataCache = new ArrayList<>();
        List<String> stringCache = new ArrayList<>();
        
        int iteration = 0;
        while (System.currentTimeMillis() < endTime) {
            iteration++;
            
            // CPU-intensive: String hashing and manipulation
            try {
                MessageDigest digest = MessageDigest.getInstance("SHA-256");
                
                // Create large strings for hashing
                StringBuilder dataBuilder = new StringBuilder();
                dataBuilder.append(transactionId).append(iteration)
                          .append(request.getCustomerEmail())
                          .append(request.getCustomerName())
                          .append(request.getStoreLocation())
                          .append(request.getTerminalId())
                          .append(request.getTotalAmount())
                          .append(System.nanoTime());
                
                // Repeat to make it larger
                String baseData = dataBuilder.toString();
                for (int i = 0; i < 10; i++) {
                    dataBuilder.append(baseData);
                }
                
                // CPU-intensive: Hash calculation
                byte[] hashBytes = digest.digest(dataBuilder.toString().getBytes("UTF-8"));
                
                // CPU-intensive: Convert to hex
                StringBuilder hexString = new StringBuilder();
                for (byte b : hashBytes) {
                    String hex = Integer.toHexString(0xff & b);
                    if (hex.length() == 1) hexString.append('0');
                    hexString.append(hex);
                }
                
                // Memory-intensive: Store in cache
                stringCache.add(hexString.toString());
                
                // Memory-intensive: Create complex objects
                Map<String, Object> cacheEntry = new HashMap<>();
                cacheEntry.put("iteration", iteration);
                cacheEntry.put("hash", hexString.toString());
                cacheEntry.put("timestamp", System.currentTimeMillis());
                cacheEntry.put("data", baseData.substring(0, Math.min(100, baseData.length())));
                dataCache.add(cacheEntry);
                
                // CPU-intensive: Mathematical operations
                double result = 0.0;
                for (int i = 1; i < 1000; i++) {
                    result += Math.sqrt(i) * Math.log(i) / Math.sin(i + 1);
                    result = Math.abs(result % 1000000);
                }
                
                // Memory management: Keep cache size reasonable
                if (stringCache.size() > 100) {
                    stringCache.subList(0, 50).clear();
                }
                if (dataCache.size() > 50) {
                    dataCache.subList(0, 25).clear();
                }
                
            } catch (Exception e) {
                log.warn("Error in heavy computation", e);
            }
            
            if (iteration % 100 == 0) {  // Only sleep every 100 iterations
                try {
                    Thread.sleep(1);
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    break;
                }
            }
        }
        
        long actualDuration = System.currentTimeMillis() - startTime;
        log.info("✅ Processing completed for transaction {} - actual duration: {} ms (target was {} ms), {} iterations", 
                 transactionId, actualDuration, durationMs, iteration);
    }

    private void performStatusCheckProcessing(String transactionId, int durationMs) {
        long startTime = System.currentTimeMillis();
        long endTime = startTime + durationMs;
        
        log.debug("Status check processing for transaction {}", transactionId);
        
        List<String> hashCache = new ArrayList<>();
        int iteration = 0;
        
        while (System.currentTimeMillis() < endTime) {
            iteration++;
            
            try {
                MessageDigest digest = MessageDigest.getInstance("SHA-256");
                
                StringBuilder data = new StringBuilder();
                data.append(transactionId).append(iteration).append(System.nanoTime());
                
                String baseData = data.toString();
                for (int i = 0; i < 5; i++) {
                    data.append(baseData);
                }
                
                byte[] hashBytes = digest.digest(data.toString().getBytes("UTF-8"));
                
                StringBuilder hexString = new StringBuilder();
                for (byte b : hashBytes) {
                    String hex = Integer.toHexString(0xff & b);
                    if (hex.length() == 1) hexString.append('0');
                    hexString.append(hex);
                }
                
                hashCache.add(hexString.toString());
                
                double result = 0.0;
                for (int i = 1; i < 500; i++) {
                    result += Math.sqrt(i) * Math.log(i);
                    result = Math.abs(result % 100000);
                }
                
                if (hashCache.size() > 50) {
                    hashCache.subList(0, 25).clear();
                }
                
            } catch (Exception e) {
                log.warn("Error in status check processing", e);
            }
            
            if (iteration % 100 == 0) {
                try {
                    Thread.sleep(1);
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    break;
                }
            }
        }
        
        log.debug("Status check processing completed: {} ms, {} iterations", 
                 System.currentTimeMillis() - startTime, iteration);
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
