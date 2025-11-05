/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */

package frauddetection

import org.apache.logging.log4j.LogManager
import org.apache.logging.log4j.Logger
import oteldemo.Demo.OrderResult
import java.sql.Timestamp
import java.time.Instant

data class FraudAlert(
    val orderId: String,
    val alertType: String,
    val severity: String,
    val reason: String,
    val riskScore: Double,
    val detectedAt: Timestamp = Timestamp.from(Instant.now())
)

class FraudAnalytics {
    private val logger: Logger = LogManager.getLogger(FraudAnalytics::class.java)

    companion object {
        const val SEVERITY_LOW = "LOW"
        const val SEVERITY_MEDIUM = "MEDIUM"
        const val SEVERITY_HIGH = "HIGH"
        const val SEVERITY_CRITICAL = "CRITICAL"
    }

    fun analyzeOrder(order: OrderResult): FraudAlert? {
        // Enhanced fraud detection with multiple database checks
        val riskScore = calculateRiskScore(order)

        if (riskScore > 0.5) {
            val alert = FraudAlert(
                orderId = order.orderId,
                alertType = determineAlertType(order, riskScore),
                severity = determineSeverity(riskScore),
                reason = buildReasonMessage(order, riskScore),
                riskScore = riskScore
            )

            logger.warn("Fraud alert generated: orderId=${alert.orderId}, severity=${alert.severity}, score=$riskScore")
            saveFraudAlert(alert)
            return alert
        }

        return null
    }

    private fun calculateRiskScore(order: OrderResult): Double {
        var score = 0.0

        // High value order (shipping cost > $50)
        if (order.hasShippingCost() && order.shippingCost.units >= 50) {
            score += 0.3
        }

        // Very high value (shipping cost > $100)
        if (order.hasShippingCost() && order.shippingCost.units >= 100) {
            score += 0.3
        }

        // Large quantity of items
        if (order.itemsCount > 10) {
            score += 0.2
        }

        // Very large quantity
        if (order.itemsCount > 20) {
            score += 0.2
        }

        // Check shipping to known fraud regions (example pattern)
        if (order.hasShippingAddress()) {
            val address = order.shippingAddress
            // Example: PO Boxes might be suspicious
            if (address.streetAddress.contains("P.O. Box", ignoreCase = true) ||
                address.streetAddress.contains("PO Box", ignoreCase = true)) {
                score += 0.15
            }
        }

        // DATABASE CHECKS - Enhanced fraud detection with multiple queries

        // 1. Check if country has high fraud rate (DB query)
        if (order.hasShippingAddress()) {
            val countryRiskScore = checkCountryRiskScore(order.shippingAddress.country)
            score += countryRiskScore

            // 2. Check city-specific fraud patterns (DB query)
            val cityRiskScore = checkCityRiskScore(order.shippingAddress.country, order.shippingAddress.city)
            score += cityRiskScore
        }

        // 3. Check if there are recent fraud alerts from this address (DB query)
        if (order.hasShippingAddress()) {
            val addressHistoryRisk = checkAddressHistory(order.shippingAddress.streetAddress)
            score += addressHistoryRisk
        }

        // 4. Check order velocity - multiple orders in short time (DB query)
        val velocityRisk = checkOrderVelocity(order)
        score += velocityRisk

        // 5. Check if shipping cost is unusually high for this country (DB query)
        if (order.hasShippingCost() && order.hasShippingAddress()) {
            val shippingAnomalyRisk = checkShippingCostAnomaly(
                order.shippingAddress.country,
                order.shippingCost.units.toDouble()
            )
            score += shippingAnomalyRisk
        }

        // 6. Check item count anomalies for this region (DB query)
        if (order.hasShippingAddress()) {
            val itemCountAnomalyRisk = checkItemCountAnomaly(
                order.shippingAddress.country,
                order.itemsCount
            )
            score += itemCountAnomalyRisk
        }

        return score.coerceAtMost(1.0)
    }

    /**
     * Query 1: Check if country has historically high fraud rates
     */
    private fun checkCountryRiskScore(country: String): Double {
        return try {
            DatabaseConfig.getConnection().use { conn ->
                val sql = """
                    SELECT
                        COUNT(*) as fraud_count,
                        (CAST(COUNT(*) AS FLOAT) / NULLIF(
                            (SELECT COUNT(*) FROM OrderLogs WHERE shipping_country = ?), 0
                        )) as fraud_rate
                    FROM FraudAlerts fa
                    JOIN OrderLogs o ON fa.order_id = o.order_id
                    WHERE o.shipping_country = ?
                    AND fa.detected_at >= DATEADD(DAY, -30, GETDATE())
                """.trimIndent()

                conn.prepareStatement(sql).use { stmt ->
                    stmt.setString(1, country)
                    stmt.setString(2, country)
                    val rs = stmt.executeQuery()

                    if (rs.next()) {
                        val fraudCount = rs.getInt("fraud_count")
                        val fraudRate = rs.getDouble("fraud_rate")

                        when {
                            fraudCount > 50 && fraudRate > 0.3 -> 0.4 // High risk country
                            fraudCount > 20 && fraudRate > 0.2 -> 0.25 // Medium risk
                            fraudCount > 10 && fraudRate > 0.1 -> 0.15 // Low risk
                            else -> 0.0
                        }
                    } else {
                        0.0
                    }
                }
            }
        } catch (e: Exception) {
            logger.error("Error checking country risk score for $country", e)
            0.0
        }
    }

    /**
     * Query 2: Check city-specific fraud patterns
     */
    private fun checkCityRiskScore(country: String, city: String): Double {
        return try {
            DatabaseConfig.getConnection().use { conn ->
                val sql = """
                    SELECT COUNT(*) as city_fraud_count
                    FROM FraudAlerts fa
                    JOIN OrderLogs o ON fa.order_id = o.order_id
                    WHERE o.shipping_country = ?
                    AND o.shipping_city = ?
                    AND fa.detected_at >= DATEADD(DAY, -30, GETDATE())
                """.trimIndent()

                conn.prepareStatement(sql).use { stmt ->
                    stmt.setString(1, country)
                    stmt.setString(2, city)
                    val rs = stmt.executeQuery()

                    if (rs.next()) {
                        val cityFraudCount = rs.getInt("city_fraud_count")
                        when {
                            cityFraudCount > 20 -> 0.2
                            cityFraudCount > 10 -> 0.1
                            else -> 0.0
                        }
                    } else {
                        0.0
                    }
                }
            }
        } catch (e: Exception) {
            logger.error("Error checking city risk score for $city, $country", e)
            0.0
        }
    }

    /**
     * Query 3: Check if this address has history of fraud
     */
    private fun checkAddressHistory(streetAddress: String): Double {
        return try {
            DatabaseConfig.getConnection().use { conn ->
                val sql = """
                    SELECT COUNT(*) as address_fraud_count
                    FROM FraudAlerts fa
                    JOIN OrderLogs o ON fa.order_id = o.order_id
                    WHERE o.shipping_street = ?
                    AND fa.detected_at >= DATEADD(DAY, -90, GETDATE())
                """.trimIndent()

                conn.prepareStatement(sql).use { stmt ->
                    stmt.setString(1, streetAddress)
                    val rs = stmt.executeQuery()

                    if (rs.next()) {
                        val addressFraudCount = rs.getInt("address_fraud_count")
                        when {
                            addressFraudCount > 5 -> 0.5 // Very suspicious - same address used multiple times
                            addressFraudCount > 2 -> 0.3
                            addressFraudCount > 0 -> 0.15
                            else -> 0.0
                        }
                    } else {
                        0.0
                    }
                }
            }
        } catch (e: Exception) {
            logger.error("Error checking address history", e)
            0.0
        }
    }

    /**
     * Query 4: Check order velocity - detect rapid succession of orders
     */
    private fun checkOrderVelocity(order: OrderResult): Double {
        return try {
            DatabaseConfig.getConnection().use { conn ->
                // Check for multiple orders in the last hour with similar characteristics
                val sql = """
                    SELECT COUNT(*) as recent_orders
                    FROM OrderLogs
                    WHERE created_at >= DATEADD(HOUR, -1, GETDATE())
                    AND (
                        shipping_street = ? OR
                        shipping_city = ? OR
                        (shipping_cost_units >= ? * 0.8 AND shipping_cost_units <= ? * 1.2)
                    )
                """.trimIndent()

                conn.prepareStatement(sql).use { stmt ->
                    val street = if (order.hasShippingAddress()) order.shippingAddress.streetAddress else ""
                    val city = if (order.hasShippingAddress()) order.shippingAddress.city else ""
                    val cost = if (order.hasShippingCost()) order.shippingCost.units else 0L

                    stmt.setString(1, street)
                    stmt.setString(2, city)
                    stmt.setLong(3, cost)
                    stmt.setLong(4, cost)

                    val rs = stmt.executeQuery()

                    if (rs.next()) {
                        val recentOrders = rs.getInt("recent_orders")
                        when {
                            recentOrders > 10 -> 0.4 // Very high velocity
                            recentOrders > 5 -> 0.25
                            recentOrders > 3 -> 0.15
                            else -> 0.0
                        }
                    } else {
                        0.0
                    }
                }
            }
        } catch (e: Exception) {
            logger.error("Error checking order velocity", e)
            0.0
        }
    }

    /**
     * Query 5: Check if shipping cost is anomalously high for this country
     */
    private fun checkShippingCostAnomaly(country: String, shippingCost: Double): Double {
        return try {
            DatabaseConfig.getConnection().use { conn ->
                val sql = """
                    SELECT
                        AVG(CAST(shipping_cost_units AS FLOAT)) as avg_cost,
                        STDEV(CAST(shipping_cost_units AS FLOAT)) as stddev_cost
                    FROM OrderLogs
                    WHERE shipping_country = ?
                    AND created_at >= DATEADD(DAY, -30, GETDATE())
                    AND shipping_cost_units > 0
                """.trimIndent()

                conn.prepareStatement(sql).use { stmt ->
                    stmt.setString(1, country)
                    val rs = stmt.executeQuery()

                    if (rs.next()) {
                        val avgCost = rs.getDouble("avg_cost")
                        val stddevCost = rs.getDouble("stddev_cost")

                        if (stddevCost > 0 && avgCost > 0) {
                            val zScore = (shippingCost - avgCost) / stddevCost
                            when {
                                zScore > 3.0 -> 0.3 // 3+ standard deviations above mean
                                zScore > 2.0 -> 0.2
                                zScore > 1.5 -> 0.1
                                else -> 0.0
                            }
                        } else {
                            0.0
                        }
                    } else {
                        0.0
                    }
                }
            }
        } catch (e: Exception) {
            logger.error("Error checking shipping cost anomaly for $country", e)
            0.0
        }
    }

    /**
     * Query 6: Check if item count is unusual for this region
     */
    private fun checkItemCountAnomaly(country: String, itemCount: Int): Double {
        return try {
            DatabaseConfig.getConnection().use { conn ->
                val sql = """
                    SELECT
                        AVG(CAST(items_count AS FLOAT)) as avg_items,
                        MAX(items_count) as max_items
                    FROM OrderLogs
                    WHERE shipping_country = ?
                    AND created_at >= DATEADD(DAY, -30, GETDATE())
                """.trimIndent()

                conn.prepareStatement(sql).use { stmt ->
                    stmt.setString(1, country)
                    val rs = stmt.executeQuery()

                    if (rs.next()) {
                        val avgItems = rs.getDouble("avg_items")
                        val maxItems = rs.getInt("max_items")

                        when {
                            itemCount > avgItems * 3 -> 0.25 // 3x the average
                            itemCount > avgItems * 2 -> 0.15
                            itemCount > maxItems -> 0.2 // Exceeds historical max
                            else -> 0.0
                        }
                    } else {
                        0.0
                    }
                }
            }
        } catch (e: Exception) {
            logger.error("Error checking item count anomaly for $country", e)
            0.0
        }
    }

    private fun determineAlertType(order: OrderResult, riskScore: Double): String {
        return when {
            order.hasShippingCost() && order.shippingCost.units >= 100 -> "HIGH_VALUE_ORDER"
            order.itemsCount > 20 -> "BULK_ORDER"
            riskScore >= 0.8 -> "CRITICAL_RISK"
            else -> "SUSPICIOUS_PATTERN"
        }
    }

    private fun determineSeverity(riskScore: Double): String {
        return when {
            riskScore >= 0.9 -> SEVERITY_CRITICAL
            riskScore >= 0.7 -> SEVERITY_HIGH
            riskScore >= 0.5 -> SEVERITY_MEDIUM
            else -> SEVERITY_LOW
        }
    }

    private fun buildReasonMessage(order: OrderResult, riskScore: Double): String {
        val reasons = mutableListOf<String>()

        if (order.hasShippingCost() && order.shippingCost.units >= 100) {
            reasons.add("Very high shipping cost: \$${order.shippingCost.units}")
        } else if (order.hasShippingCost() && order.shippingCost.units >= 50) {
            reasons.add("High shipping cost: \$${order.shippingCost.units}")
        }

        if (order.itemsCount > 20) {
            reasons.add("Very large quantity: ${order.itemsCount} items")
        } else if (order.itemsCount > 10) {
            reasons.add("Large quantity: ${order.itemsCount} items")
        }

        if (order.hasShippingAddress()) {
            val address = order.shippingAddress
            if (address.streetAddress.contains("P.O. Box", ignoreCase = true)) {
                reasons.add("PO Box shipping address")
            }
        }

        if (reasons.isEmpty()) {
            reasons.add("Multiple risk factors detected")
        }

        return reasons.joinToString("; ")
    }

    private fun saveFraudAlert(alert: FraudAlert): Boolean {
        return try {
            DatabaseConfig.getConnection().use { conn ->
                val sql = """
                    INSERT INTO FraudAlerts (
                        order_id,
                        alert_type,
                        severity,
                        reason,
                        risk_score,
                        detected_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """.trimIndent()

                conn.prepareStatement(sql).use { stmt ->
                    stmt.setString(1, alert.orderId)
                    stmt.setString(2, alert.alertType)
                    stmt.setString(3, alert.severity)
                    stmt.setString(4, alert.reason)
                    stmt.setDouble(5, alert.riskScore)
                    stmt.setTimestamp(6, alert.detectedAt)

                    val rowsAffected = stmt.executeUpdate()
                    if (rowsAffected > 0) {
                        logger.info("Saved fraud alert for order ${alert.orderId}")
                        true
                    } else {
                        logger.warn("Failed to save fraud alert for order ${alert.orderId}")
                        false
                    }
                }
            }
        } catch (e: Exception) {
            logger.error("Error saving fraud alert for order ${alert.orderId}", e)
            false
        }
    }

    // Analytics queries
    fun getAlertStats(hours: Int = 24): Map<String, Any> {
        return try {
            DatabaseConfig.getConnection().use { conn ->
                val sql = """
                    SELECT
                        COUNT(*) as total_alerts,
                        AVG(risk_score) as avg_risk_score,
                        MAX(risk_score) as max_risk_score,
                        SUM(CASE WHEN severity = 'CRITICAL' THEN 1 ELSE 0 END) as critical_count,
                        SUM(CASE WHEN severity = 'HIGH' THEN 1 ELSE 0 END) as high_count,
                        SUM(CASE WHEN severity = 'MEDIUM' THEN 1 ELSE 0 END) as medium_count,
                        SUM(CASE WHEN severity = 'LOW' THEN 1 ELSE 0 END) as low_count
                    FROM FraudAlerts
                    WHERE detected_at >= DATEADD(HOUR, -?, GETDATE())
                """.trimIndent()

                conn.prepareStatement(sql).use { stmt ->
                    stmt.setInt(1, hours)
                    val rs = stmt.executeQuery()

                    if (rs.next()) {
                        mapOf(
                            "total_alerts" to rs.getInt("total_alerts"),
                            "avg_risk_score" to rs.getDouble("avg_risk_score"),
                            "max_risk_score" to rs.getDouble("max_risk_score"),
                            "critical_count" to rs.getInt("critical_count"),
                            "high_count" to rs.getInt("high_count"),
                            "medium_count" to rs.getInt("medium_count"),
                            "low_count" to rs.getInt("low_count"),
                            "hours" to hours
                        )
                    } else {
                        emptyMap()
                    }
                }
            }
        } catch (e: Exception) {
            logger.error("Error getting alert stats", e)
            emptyMap()
        }
    }

    fun getTopRiskyCountries(limit: Int = 10): List<Map<String, Any>> {
        return try {
            DatabaseConfig.getConnection().use { conn ->
                val sql = """
                    SELECT TOP (?)
                        o.shipping_country,
                        COUNT(fa.id) as alert_count,
                        AVG(fa.risk_score) as avg_risk_score
                    FROM FraudAlerts fa
                    JOIN OrderLogs o ON fa.order_id = o.order_id
                    WHERE o.shipping_country IS NOT NULL
                    GROUP BY o.shipping_country
                    ORDER BY alert_count DESC, avg_risk_score DESC
                """.trimIndent()

                conn.prepareStatement(sql).use { stmt ->
                    stmt.setInt(1, limit)
                    val rs = stmt.executeQuery()

                    val results = mutableListOf<Map<String, Any>>()
                    while (rs.next()) {
                        results.add(mapOf(
                            "country" to rs.getString("shipping_country"),
                            "alert_count" to rs.getInt("alert_count"),
                            "avg_risk_score" to rs.getDouble("avg_risk_score")
                        ))
                    }
                    results
                }
            }
        } catch (e: Exception) {
            logger.error("Error getting top risky countries", e)
            emptyList()
        }
    }
}
