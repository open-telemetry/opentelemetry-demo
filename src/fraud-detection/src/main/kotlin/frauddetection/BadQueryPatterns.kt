/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */

package frauddetection

import org.apache.logging.log4j.LogManager
import org.apache.logging.log4j.Logger
import kotlin.random.Random

/**
 * Executes intentionally inefficient database queries to demonstrate
 * database monitoring and performance analysis capabilities.
 *
 * WARNING: These queries are intentionally bad for demo purposes only!
 * They demonstrate:
 * - Full table scans without indexes
 * - N+1 query problems
 * - Missing WHERE clauses
 * - Inefficient JOIN patterns
 * - Excessive data retrieval
 */
class BadQueryPatterns {
    private val logger: Logger = LogManager.getLogger(BadQueryPatterns::class.java)

    /**
     * Randomly executes one of several intentionally bad query patterns.
     * Returns true if a bad query was executed.
     * @param executionPercentage The percentage (0-100) chance to execute a bad query
     */
    fun maybeExecuteBadQuery(executionPercentage: Int): Boolean {
        if (executionPercentage <= 0 || Random.nextInt(100) >= executionPercentage) {
            return false
        }

        val queryType = Random.nextInt(6)

        try {
            when (queryType) {
                0 -> fullTableScanWithoutWhere()
                1 -> selectStarFromLargeTables()
                2 -> inefficientLikeQuery()
                3 -> redundantSubquery()
                4 -> nPlusOnePattern()
                5 -> expensiveAggregationWithoutIndex()
            }
            return true
        } catch (e: Exception) {
            logger.error("Error executing bad query pattern $queryType", e)
            return false
        }
    }

    /**
     * Pattern 1: Full table scan without WHERE clause
     * Impact: Reads entire table, high I/O, slow performance
     */
    private fun fullTableScanWithoutWhere() {
        DatabaseConfig.getConnection().use { conn ->
            val sql = """
                SELECT COUNT(*) as total
                FROM OrderLogs
            """.trimIndent()

            conn.createStatement().use { stmt ->
                stmt.executeQuery(sql).use { rs ->
                    if (rs.next()) {
                        val count = rs.getInt("total")
                        logger.warn("⚠️ BAD QUERY: Full table scan on OrderLogs, total=$count")
                    }
                }
            }
        }
    }

    /**
     * Pattern 2: SELECT * from large tables
     * Impact: Excessive data transfer, memory usage
     */
    private fun selectStarFromLargeTables() {
        DatabaseConfig.getConnection().use { conn ->
            val sql = """
                SELECT TOP 1000 *
                FROM OrderLogs
            """.trimIndent()

            conn.createStatement().use { stmt ->
                stmt.executeQuery(sql).use { rs ->
                    var rowCount = 0
                    while (rs.next()) {
                        rowCount++
                        // Intentionally retrieve all columns but don't use them
                        rs.getString("order_id")
                        rs.getString("items_json")
                    }
                    logger.warn("⚠️ BAD QUERY: SELECT * retrieved $rowCount rows with all columns")
                }
            }
        }
    }

    /**
     * Pattern 3: Inefficient LIKE query without proper indexing
     * Impact: Can't use index effectively, full table scan
     */
    private fun inefficientLikeQuery() {
        DatabaseConfig.getConnection().use { conn ->
            val sql = """
                SELECT order_id, shipping_street
                FROM OrderLogs
                WHERE shipping_street LIKE '%Box%'
            """.trimIndent()

            conn.createStatement().use { stmt ->
                stmt.executeQuery(sql).use { rs ->
                    var matchCount = 0
                    while (rs.next()) {
                        matchCount++
                    }
                    logger.warn("⚠️ BAD QUERY: Inefficient LIKE with leading wildcard, matches=$matchCount")
                }
            }
        }
    }

    /**
     * Pattern 4: Redundant subquery that could be simplified
     * Impact: Multiple query executions, inefficient execution plan
     */
    private fun redundantSubquery() {
        DatabaseConfig.getConnection().use { conn ->
            val sql = """
                SELECT o.order_id, o.shipping_cost_units,
                    (SELECT COUNT(*) FROM FraudAlerts WHERE order_id = o.order_id) as alert_count
                FROM OrderLogs o
                WHERE o.id > (SELECT MAX(id) - 100 FROM OrderLogs)
            """.trimIndent()

            conn.createStatement().use { stmt ->
                stmt.executeQuery(sql).use { rs ->
                    var rowCount = 0
                    while (rs.next()) {
                        rowCount++
                    }
                    logger.warn("⚠️ BAD QUERY: Redundant correlated subquery, processed $rowCount rows")
                }
            }
        }
    }

    /**
     * Pattern 5: N+1 query problem simulation
     * Impact: Multiple round trips to database, high latency
     */
    private fun nPlusOnePattern() {
        DatabaseConfig.getConnection().use { conn ->
            // First query: Get orders
            val ordersSql = "SELECT TOP 10 order_id FROM OrderLogs ORDER BY id DESC"
            val orderIds = mutableListOf<String>()

            conn.createStatement().use { stmt ->
                stmt.executeQuery(ordersSql).use { rs ->
                    while (rs.next()) {
                        orderIds.add(rs.getString("order_id"))
                    }
                }
            }

            // N queries: Get fraud alerts for each order (N+1 problem!)
            var totalQueries = 1
            orderIds.forEach { orderId ->
                val alertSql = "SELECT COUNT(*) as cnt FROM FraudAlerts WHERE order_id = ?"
                conn.prepareStatement(alertSql).use { stmt ->
                    stmt.setString(1, orderId)
                    stmt.executeQuery().use { rs ->
                        if (rs.next()) {
                            totalQueries++
                        }
                    }
                }
            }

            logger.warn("⚠️ BAD QUERY: N+1 problem, executed $totalQueries queries instead of 1 JOIN")
        }
    }

    /**
     * Pattern 6: Expensive aggregation without proper indexing
     * Impact: Full table scan for aggregation, high CPU usage
     */
    private fun expensiveAggregationWithoutIndex() {
        DatabaseConfig.getConnection().use { conn ->
            val sql = """
                SELECT
                    shipping_country,
                    shipping_city,
                    COUNT(*) as order_count,
                    AVG(CAST(shipping_cost_units AS FLOAT)) as avg_shipping_cost,
                    MAX(items_count) as max_items
                FROM OrderLogs
                WHERE shipping_country IS NOT NULL
                GROUP BY shipping_country, shipping_city
                ORDER BY order_count DESC
            """.trimIndent()

            conn.createStatement().use { stmt ->
                stmt.executeQuery(sql).use { rs ->
                    var groupCount = 0
                    while (rs.next()) {
                        groupCount++
                    }
                    logger.warn("⚠️ BAD QUERY: Expensive aggregation without index, $groupCount groups")
                }
            }
        }
    }

    /**
     * Execute a specific bad query pattern by type (for testing)
     */
    fun executeBadQueryByType(type: Int) {
        when (type) {
            0 -> fullTableScanWithoutWhere()
            1 -> selectStarFromLargeTables()
            2 -> inefficientLikeQuery()
            3 -> redundantSubquery()
            4 -> nPlusOnePattern()
            5 -> expensiveAggregationWithoutIndex()
            else -> logger.warn("Unknown bad query type: $type")
        }
    }
}
