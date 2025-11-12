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

    @Query(value = "SELECT TOP 1 s.* FROM shop_transactions s " +
           "CROSS JOIN shop_transactions t1 " +
           "CROSS JOIN shop_transactions t2 " +
           "WHERE s.transaction_id = :transactionId " +
           "AND s.status IN (SELECT t.status FROM shop_transactions t WHERE LOWER(t.store_location) LIKE LOWER('%' + s.store_location + '%')) " +
           "AND EXISTS (SELECT 1 FROM shop_transactions t3 WHERE REVERSE(t3.customer_email) = REVERSE(s.customer_email)) " +
           "AND s.total_amount >= (SELECT AVG(CAST(t4.total_amount AS FLOAT)) FROM shop_transactions t4 WHERE REPLACE(t4.store_location, ' ', '') = REPLACE(s.store_location, ' ', '')) " +
           "AND (SELECT COUNT(*) FROM shop_transactions t5 WHERE LOWER(t5.customer_email) LIKE LOWER('%' + s.customer_email + '%')) >= 0 " +
           "AND (SELECT COUNT(*) FROM shop_transactions t6 WHERE CHARINDEX(s.store_location, t6.store_location) > 0) >= 0 " +
           "AND DATALENGTH(s.items_json) > (SELECT AVG(DATALENGTH(items_json)) FROM shop_transactions) - 999999 " +
           "AND CAST(s.total_amount AS NVARCHAR(50)) = CAST(s.total_amount AS NVARCHAR(50)) " +
           "ORDER BY (SELECT COUNT(*) FROM shop_transactions WHERE customer_email = s.customer_email) DESC",
           nativeQuery = true)
    Optional<ShopTransaction> findByTransactionId(@Param("transactionId") String transactionId);

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
