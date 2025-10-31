// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

package com.opentelemetry.demo.shopdcshim.entity;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Entity
@Table(name = "shop_transactions")
@Data
@NoArgsConstructor
@AllArgsConstructor
public class ShopTransaction {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "transaction_id", unique = true, nullable = false)
    private String transactionId;

    @Column(name = "local_order_id", nullable = false)
    private String localOrderId;

    @Column(name = "cloud_order_id")
    private String cloudOrderId;

    @Column(name = "customer_email", nullable = false)
    private String customerEmail;

    @Column(name = "customer_name")
    private String customerName;

    @Column(name = "total_amount", precision = 10, scale = 2)
    private BigDecimal totalAmount;

    @Column(name = "currency_code", length = 3)
    private String currencyCode;

    @Column(name = "status")
    @Enumerated(EnumType.STRING)
    private TransactionStatus status;

    @Column(name = "store_location", length = 100)
    private String storeLocation;

    @Column(name = "terminal_id", length = 50)
    private String terminalId;

    @Column(name = "created_at")
    private LocalDateTime createdAt;

    @Column(name = "processed_at")
    private LocalDateTime processedAt;

    @Column(name = "cloud_submitted_at")
    private LocalDateTime cloudSubmittedAt;

    @Column(name = "cloud_confirmed_at")
    private LocalDateTime cloudConfirmedAt;

    @Column(name = "error_message")
    private String errorMessage;

    @Column(name = "retry_count")
    private Integer retryCount;

    // Shipping address stored as JSON-like string for simplicity
    @Column(name = "shipping_address", columnDefinition = "TEXT")
    private String shippingAddress;

    // Items purchased (simplified for demo)
    @Column(name = "items_json", columnDefinition = "TEXT")
    private String itemsJson;

    @PrePersist
    protected void onCreate() {
        createdAt = LocalDateTime.now();
        if (retryCount == null) {
            retryCount = 0;
        }
    }

    public enum TransactionStatus {
        INITIATED,          
        VALIDATING,         
        SUBMITTING_CLOUD,   
        CLOUD_PROCESSING,   
        COMPLETED,          
        FAILED,            
        RETRY_PENDING      
    }
}
