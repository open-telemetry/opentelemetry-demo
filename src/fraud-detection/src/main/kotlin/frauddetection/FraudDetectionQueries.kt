/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */

package frauddetection

import org.apache.logging.log4j.LogManager
import org.apache.logging.log4j.Logger
import kotlin.random.Random

/**
 * Executes SQL-based fraud detection queries with varying latency.
 * These queries simulate automatic fraud detection analysis that runs
 * after an order is logged, demonstrating realistic database monitoring patterns.
 */
class FraudDetectionQueries {
    private val logger: Logger = LogManager.getLogger(FraudDetectionQueries::class.java)

    /**
     * Run fraud detection analysis on a newly inserted order.
     * Randomly executes 1-3 fraud detection queries with latency variance.
     * @param orderId The order ID to analyze
     * @return true if any fraud indicators were found
     */
    fun analyzeOrder(orderId: String): Boolean {
        val numChecks = Random.nextInt(1, 4) // Run 1-3 checks randomly
        var fraudDetected = false

        try {
            val checksToRun = (0..5).shuffled().take(numChecks)

            checksToRun.forEach { checkType ->
                val result = when (checkType) {
                    0 -> checkHighValueOrder(orderId)
                    1 -> checkDuplicateShippingAddress(orderId)
                    2 -> checkRapidOrderVelocity(orderId)
                    3 -> checkSuspiciousCountryPattern(orderId)
                    4 -> checkAnomalousItemCount(orderId)
                    5 -> checkHistoricalFraudPatterns(orderId)
                    else -> false
                }
                if (result) fraudDetected = true
            }
        } catch (e: Exception) {
            logger.error("Error during fraud detection for order $orderId", e)
        }

        return fraudDetected
    }

    /**
     * Check 1: High-value order detection with historical comparison
     * Latency: 50-200ms (medium complexity query with aggregation)
     */
    private fun checkHighValueOrder(orderId: String): Boolean {
        DatabaseConfig.getConnection().use { conn ->
            // Simulate variable latency
            Thread.sleep(Random.nextLong(50, 200))

            val sql = """
                WITH OrderValue AS (
                    SELECT
                        order_id,
                        shipping_cost_units,
                        items_count,
                        (shipping_cost_units + (items_count * 50)) as estimated_value
                    FROM OrderLogs
                    WHERE order_id = ?
                ),
                AvgValue AS (
                    SELECT AVG(shipping_cost_units + (items_count * 50)) as avg_order_value
                    FROM OrderLogs
                    WHERE consumed_at >= DATEADD(HOUR, -24, GETDATE())
                )
                SELECT
                    CASE
                        WHEN ov.estimated_value > (av.avg_order_value * 3) THEN 1
                        ELSE 0
                    END as is_high_value
                FROM OrderValue ov, AvgValue av
            """.trimIndent()

            conn.prepareStatement(sql).use { stmt ->
                stmt.setString(1, orderId)
                stmt.executeQuery().use { rs ->
                    if (rs.next() && rs.getInt("is_high_value") == 1) {
                        logger.warn("🔍 FRAUD CHECK: High-value order detected for $orderId (>3x avg)")
                        return true
                    }
                }
            }
        }
        return false
    }

    /**
     * Check 2: Duplicate shipping address with recent orders
     * Latency: 100-300ms (complex string matching and temporal query)
     */
    private fun checkDuplicateShippingAddress(orderId: String): Boolean {
        DatabaseConfig.getConnection().use { conn ->
            // Simulate variable latency
            Thread.sleep(Random.nextLong(100, 300))

            val sql = """
                WITH CurrentOrder AS (
                    SELECT shipping_street, shipping_city, shipping_zip
                    FROM OrderLogs
                    WHERE order_id = ?
                )
                SELECT COUNT(DISTINCT ol.order_id) as duplicate_count
                FROM OrderLogs ol, CurrentOrder co
                WHERE ol.shipping_street = co.shipping_street
                    AND ol.shipping_city = co.shipping_city
                    AND ol.shipping_zip = co.shipping_zip
                    AND ol.order_id != ?
                    AND ol.consumed_at >= DATEADD(HOUR, -1, GETDATE())
            """.trimIndent()

            conn.prepareStatement(sql).use { stmt ->
                stmt.setString(1, orderId)
                stmt.setString(2, orderId)
                stmt.executeQuery().use { rs ->
                    if (rs.next()) {
                        val dupes = rs.getInt("duplicate_count")
                        if (dupes >= 3) {
                            logger.warn("🔍 FRAUD CHECK: Duplicate shipping address for $orderId ($dupes recent orders)")
                            insertFraudAlert(orderId, "DUPLICATE_ADDRESS", "MEDIUM", dupes * 0.15)
                            return true
                        }
                    }
                }
            }
        }
        return false
    }

    /**
     * Check 3: Rapid order velocity from same location
     * Latency: 80-250ms (temporal aggregation with grouping)
     */
    private fun checkRapidOrderVelocity(orderId: String): Boolean {
        DatabaseConfig.getConnection().use { conn ->
            // Simulate variable latency
            Thread.sleep(Random.nextLong(80, 250))

            val sql = """
                WITH CurrentOrder AS (
                    SELECT shipping_city, shipping_state, shipping_country, consumed_at
                    FROM OrderLogs
                    WHERE order_id = ?
                )
                SELECT
                    COUNT(*) as order_count,
                    COUNT(DISTINCT order_id) as unique_orders,
                    DATEDIFF(MINUTE, MIN(ol.consumed_at), MAX(ol.consumed_at)) as time_span_minutes
                FROM OrderLogs ol
                INNER JOIN CurrentOrder co ON
                    ol.shipping_city = co.shipping_city AND
                    ol.shipping_state = co.shipping_state AND
                    ol.shipping_country = co.shipping_country
                WHERE ol.consumed_at >= DATEADD(MINUTE, -15, GETDATE())
                HAVING COUNT(*) >= 5
            """.trimIndent()

            conn.prepareStatement(sql).use { stmt ->
                stmt.setString(1, orderId)
                stmt.executeQuery().use { rs ->
                    if (rs.next()) {
                        val orderCount = rs.getInt("order_count")
                        val timeSpan = rs.getInt("time_span_minutes")
                        if (orderCount >= 5) {
                            val riskScore = (orderCount / 5.0) * 0.25
                            logger.warn("🔍 FRAUD CHECK: Rapid order velocity for $orderId ($orderCount orders in $timeSpan mins)")
                            insertFraudAlert(orderId, "RAPID_VELOCITY", "HIGH", riskScore)
                            return true
                        }
                    }
                }
            }
        }
        return false
    }

    /**
     * Check 4: Suspicious country/region pattern analysis
     * Latency: 120-350ms (complex geo-pattern with historical joins)
     */
    private fun checkSuspiciousCountryPattern(orderId: String): Boolean {
        DatabaseConfig.getConnection().use { conn ->
            // Simulate variable latency
            Thread.sleep(Random.nextLong(120, 350))

            val sql = """
                WITH OrderCountry AS (
                    SELECT shipping_country, shipping_state
                    FROM OrderLogs
                    WHERE order_id = ?
                ),
                CountryStats AS (
                    SELECT
                        shipping_country,
                        COUNT(*) as total_orders,
                        AVG(CAST(shipping_cost_units AS FLOAT)) as avg_shipping_cost,
                        COUNT(DISTINCT shipping_city) as unique_cities
                    FROM OrderLogs
                    WHERE consumed_at >= DATEADD(DAY, -7, GETDATE())
                    GROUP BY shipping_country
                )
                SELECT
                    cs.total_orders,
                    cs.avg_shipping_cost,
                    cs.unique_cities,
                    CASE
                        WHEN cs.total_orders < 5 THEN 1
                        WHEN cs.avg_shipping_cost > 100 THEN 1
                        ELSE 0
                    END as is_suspicious
                FROM OrderCountry oc
                LEFT JOIN CountryStats cs ON oc.shipping_country = cs.shipping_country
            """.trimIndent()

            conn.prepareStatement(sql).use { stmt ->
                stmt.setString(1, orderId)
                stmt.executeQuery().use { rs ->
                    if (rs.next() && rs.getInt("is_suspicious") == 1) {
                        val totalOrders = rs.getInt("total_orders")
                        logger.warn("🔍 FRAUD CHECK: Suspicious country pattern for $orderId (rare country: $totalOrders orders)")
                        insertFraudAlert(orderId, "SUSPICIOUS_LOCATION", "MEDIUM", 0.35)
                        return true
                    }
                }
            }
        }
        return false
    }

    /**
     * Check 5: Anomalous item count with statistical analysis
     * Latency: 60-180ms (statistical aggregation query)
     */
    private fun checkAnomalousItemCount(orderId: String): Boolean {
        DatabaseConfig.getConnection().use { conn ->
            // Simulate variable latency
            Thread.sleep(Random.nextLong(60, 180))

            val sql = """
                WITH CurrentOrder AS (
                    SELECT items_count
                    FROM OrderLogs
                    WHERE order_id = ?
                ),
                ItemStats AS (
                    SELECT
                        AVG(CAST(items_count AS FLOAT)) as avg_items,
                        STDEV(CAST(items_count AS FLOAT)) as stddev_items
                    FROM OrderLogs
                    WHERE consumed_at >= DATEADD(DAY, -1, GETDATE())
                )
                SELECT
                    co.items_count,
                    is_stat.avg_items,
                    is_stat.stddev_items,
                    CASE
                        WHEN co.items_count > (is_stat.avg_items + (2 * is_stat.stddev_items)) THEN 1
                        ELSE 0
                    END as is_anomalous
                FROM CurrentOrder co, ItemStats is_stat
            """.trimIndent()

            conn.prepareStatement(sql).use { stmt ->
                stmt.setString(1, orderId)
                stmt.executeQuery().use { rs ->
                    if (rs.next() && rs.getInt("is_anomalous") == 1) {
                        val itemCount = rs.getInt("items_count")
                        logger.warn("🔍 FRAUD CHECK: Anomalous item count for $orderId (count: $itemCount, >2σ from mean)")
                        insertFraudAlert(orderId, "ANOMALOUS_ITEMS", "LOW", 0.20)
                        return true
                    }
                }
            }
        }
        return false
    }

    /**
     * Check 6: Historical fraud pattern matching with correlated subqueries
     * Latency: 150-400ms (expensive multi-table joins and correlation)
     */
    private fun checkHistoricalFraudPatterns(orderId: String): Boolean {
        DatabaseConfig.getConnection().use { conn ->
            // Simulate variable latency
            Thread.sleep(Random.nextLong(150, 400))

            val sql = """
                WITH CurrentOrder AS (
                    SELECT shipping_street, shipping_city, shipping_country, items_count
                    FROM OrderLogs
                    WHERE order_id = ?
                ),
                HistoricalFraud AS (
                    SELECT DISTINCT TOP 100 fa.order_id, ol.shipping_street, ol.shipping_city
                    FROM FraudAlerts fa
                    INNER JOIN OrderLogs ol ON fa.order_id = ol.order_id
                    WHERE fa.severity IN ('HIGH', 'CRITICAL')
                        AND fa.detected_at >= DATEADD(DAY, -30, GETDATE())
                )
                SELECT
                    COUNT(DISTINCT hf.order_id) as matching_fraud_patterns
                FROM CurrentOrder co
                INNER JOIN HistoricalFraud hf ON
                    (co.shipping_street = hf.shipping_street OR co.shipping_city = hf.shipping_city)
                HAVING COUNT(DISTINCT hf.order_id) > 0
            """.trimIndent()

            conn.prepareStatement(sql).use { stmt ->
                stmt.setString(1, orderId)
                stmt.executeQuery().use { rs ->
                    if (rs.next()) {
                        val matchCount = rs.getInt("matching_fraud_patterns")
                        if (matchCount > 0) {
                            val riskScore = Math.min(matchCount * 0.30, 0.90)
                            logger.warn("🔍 FRAUD CHECK: Historical fraud pattern match for $orderId ($matchCount similar patterns)")
                            insertFraudAlert(orderId, "HISTORICAL_PATTERN", "HIGH", riskScore)
                            return true
                        }
                    }
                }
            }
        }
        return false
    }

    /**
     * Insert a fraud alert record into the FraudAlerts table
     */
    private fun insertFraudAlert(orderId: String, alertType: String, severity: String, riskScore: Double) {
        try {
            DatabaseConfig.getConnection().use { conn ->
                val sql = """
                    INSERT INTO FraudAlerts (order_id, alert_type, severity, risk_score, reason)
                    VALUES (?, ?, ?, ?, ?)
                """.trimIndent()

                conn.prepareStatement(sql).use { stmt ->
                    stmt.setString(1, orderId)
                    stmt.setString(2, alertType)
                    stmt.setString(3, severity)
                    stmt.setDouble(4, riskScore)
                    stmt.setString(5, "Automatic fraud detection triggered for $alertType")

                    stmt.executeUpdate()
                    logger.info("📝 Fraud alert created for order $orderId: $alertType ($severity, risk: $riskScore)")
                }
            }
        } catch (e: Exception) {
            logger.error("Failed to insert fraud alert for order $orderId", e)
        }
    }
}
