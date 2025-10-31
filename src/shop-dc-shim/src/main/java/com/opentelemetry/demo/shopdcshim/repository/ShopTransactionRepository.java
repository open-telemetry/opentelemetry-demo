// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

package com.opentelemetry.demo.shopdcshim.repository;

import com.opentelemetry.demo.shopdcshim.entity.ShopTransaction;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

@Repository
public interface ShopTransactionRepository extends JpaRepository<ShopTransaction, Long> {

    Optional<ShopTransaction> findByTransactionId(String transactionId);

    Optional<ShopTransaction> findByLocalOrderId(String localOrderId);

    Optional<ShopTransaction> findByCloudOrderId(String cloudOrderId);

    List<ShopTransaction> findByStatus(ShopTransaction.TransactionStatus status);

    @Query("SELECT s FROM ShopTransaction s WHERE s.status = :status AND s.createdAt < :cutoffTime")
    List<ShopTransaction> findStaleTransactionsByStatus(
        @Param("status") ShopTransaction.TransactionStatus status,
        @Param("cutoffTime") LocalDateTime cutoffTime);

    @Query("SELECT COUNT(s) FROM ShopTransaction s WHERE s.status = :status")
    long countByStatus(@Param("status") ShopTransaction.TransactionStatus status);

    @Query("SELECT s FROM ShopTransaction s WHERE s.storeLocation = :storeLocation AND s.createdAt >= :since")
    List<ShopTransaction> findByStoreLocationAndCreatedAtAfter(
        @Param("storeLocation") String storeLocation,
        @Param("since") LocalDateTime since);

    @Query("SELECT COUNT(s) FROM ShopTransaction s WHERE s.createdAt >= :since AND s.status = 'COMPLETED'")
    long countCompletedTransactionsSince(@Param("since") LocalDateTime since);

    @Query(value = "SELECT AVG(DATEDIFF(SECOND, created_at, cloud_confirmed_at)) " +
           "FROM shop_transactions WHERE status = 'COMPLETED' AND created_at >= :since", 
           nativeQuery = true)
    Double getAverageProcessingTimeSeconds(@Param("since") LocalDateTime since);
}
