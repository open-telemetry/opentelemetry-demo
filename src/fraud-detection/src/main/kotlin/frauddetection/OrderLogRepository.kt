/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */

package frauddetection

import org.apache.logging.log4j.LogManager
import org.apache.logging.log4j.Logger
import oteldemo.Demo.OrderResult
import com.google.protobuf.util.JsonFormat
import java.sql.Timestamp
import java.time.Instant

class OrderLogRepository {
    private val logger: Logger = LogManager.getLogger(OrderLogRepository::class.java)
    private val jsonPrinter = JsonFormat.printer()

    fun saveOrder(orderResult: OrderResult): Boolean {
        return try {
            DatabaseConfig.getConnection().use { conn ->
                val sql = """
                    INSERT INTO OrderLogs (
                        order_id,
                        shipping_tracking_id,
                        shipping_cost_currency,
                        shipping_cost_units,
                        shipping_cost_nanos,
                        shipping_street,
                        shipping_city,
                        shipping_state,
                        shipping_country,
                        shipping_zip,
                        items_count,
                        items_json,
                        consumed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """.trimIndent()

                conn.prepareStatement(sql).use { stmt ->
                    stmt.setString(1, orderResult.orderId)
                    stmt.setString(2, orderResult.shippingTrackingId)

                    // Shipping cost
                    if (orderResult.hasShippingCost()) {
                        stmt.setString(3, orderResult.shippingCost.currencyCode)
                        stmt.setLong(4, orderResult.shippingCost.units)
                        stmt.setInt(5, orderResult.shippingCost.nanos)
                    } else {
                        stmt.setNull(3, java.sql.Types.NVARCHAR)
                        stmt.setNull(4, java.sql.Types.BIGINT)
                        stmt.setNull(5, java.sql.Types.INTEGER)
                    }

                    // Shipping address
                    if (orderResult.hasShippingAddress()) {
                        stmt.setString(6, orderResult.shippingAddress.streetAddress)
                        stmt.setString(7, orderResult.shippingAddress.city)
                        stmt.setString(8, orderResult.shippingAddress.state)
                        stmt.setString(9, orderResult.shippingAddress.country)
                        stmt.setString(10, orderResult.shippingAddress.zipCode)
                    } else {
                        stmt.setNull(6, java.sql.Types.NVARCHAR)
                        stmt.setNull(7, java.sql.Types.NVARCHAR)
                        stmt.setNull(8, java.sql.Types.NVARCHAR)
                        stmt.setNull(9, java.sql.Types.NVARCHAR)
                        stmt.setNull(10, java.sql.Types.NVARCHAR)
                    }

                    // Items
                    stmt.setInt(11, orderResult.itemsCount)

                    // Convert items to JSON
                    val itemsJson = jsonPrinter.print(orderResult)
                    stmt.setString(12, itemsJson)

                    // Timestamp
                    stmt.setTimestamp(13, Timestamp.from(Instant.now()))

                    val rowsAffected = stmt.executeUpdate()
                    if (rowsAffected > 0) {
                        logger.info("Successfully saved order ${orderResult.orderId} to database")
                        true
                    } else {
                        logger.warn("Failed to save order ${orderResult.orderId} - no rows affected")
                        false
                    }
                }
            }
        } catch (e: Exception) {
            logger.error("Error saving order ${orderResult.orderId} to database", e)
            false
        }
    }
}
