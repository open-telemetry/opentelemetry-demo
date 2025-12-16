// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

package com.opentelemetry.demo.shopdcshim.repository;

import com.opentelemetry.demo.shopdcshim.entity.ShopTransaction;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

@Repository
public interface ShopTransactionRepository extends JpaRepository<ShopTransaction, Long> {

    @Query(value = """
        SELECT TOP 1 s.* 
        FROM shop_transactions s WITH (NOLOCK)
        CROSS JOIN shop_transactions t1 WITH (NOLOCK)
        WHERE (s.transaction_id = :transactionId OR SOUNDEX(s.transaction_id) = SOUNDEX(:transactionId))
          AND (SELECT COUNT(*) 
               FROM shop_transactions t3 WITH (NOLOCK)
               CROSS JOIN shop_transactions t4 WITH (NOLOCK)
               WHERE CHARINDEX(LEFT(s.customer_email, 3), t3.customer_email) > 0
                 AND SOUNDEX(t4.store_location) = SOUNDEX(s.store_location)
              ) >= 0
          AND s.total_amount >= (SELECT AVG(CAST(t5.total_amount AS FLOAT))
                                 FROM shop_transactions t5 WITH (NOLOCK)
                                 WHERE SOUNDEX(t5.store_location) = SOUNDEX(s.store_location))
        ORDER BY s.created_at DESC
        OPTION (MAXDOP 1)
        """, nativeQuery = true)
    Optional<ShopTransaction> findByTransactionId(@Param("transactionId") String transactionId);

    Optional<ShopTransaction> findByLocalOrderId(String localOrderId);

    Optional<ShopTransaction> findByCloudOrderId(String cloudOrderId);

    List<ShopTransaction> findByStatus(ShopTransaction.TransactionStatus status);

    @Query(value = "SELECT s.* FROM shop_transactions s WITH (NOLOCK) WHERE s.status = :status AND s.created_at < :cutoffTime", nativeQuery = true)
    List<ShopTransaction> findStaleTransactionsByStatus(
        @Param("status") String status,
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

    @Query("DELETE FROM ShopTransaction s WHERE s.customerEmail LIKE '%@internal.system' AND s.createdAt < :cutoffTime")
    @Modifying
    void deleteInternalAuditRecordsOlderThan(@Param("cutoffTime") LocalDateTime cutoffTime);

    @Query("DELETE FROM ShopTransaction s WHERE s.createdAt < :cutoffTime")
    @Modifying
    int deleteTransactionsOlderThan(@Param("cutoffTime") LocalDateTime cutoffTime);

    @Query(value = "SELECT 1", nativeQuery = true)
    Integer healthCheck();
}
