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

        // Check for high-risk countries
        val highRiskCountries = setOf("XX", "YY", "ZZ") // Placeholder
        if (order.hasShippingAddress() && order.shippingAddress.country in highRiskCountries) {
            score += 0.4
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

        return score.coerceAtMost(1.0)
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
