/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */

package frauddetection

import org.apache.logging.log4j.LogManager
import org.apache.logging.log4j.Logger
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

class DatabaseCleanup {
    private val logger: Logger = LogManager.getLogger(DatabaseCleanup::class.java)
    private val scheduler = Executors.newSingleThreadScheduledExecutor()

    fun startCleanupScheduler(retentionDays: Int = 7, intervalHours: Long = 24) {
        logger.info("Starting database cleanup scheduler: retentionDays=$retentionDays, intervalHours=$intervalHours")

        scheduler.scheduleAtFixedRate({
            try {
                cleanupOldRecords(retentionDays)
            } catch (e: Exception) {
                logger.error("Error during scheduled cleanup", e)
            }
        }, 1, intervalHours, TimeUnit.HOURS)
    }

    fun cleanupOldRecords(retentionDays: Int): Int {
        return try {
            DatabaseConfig.getConnection().use { conn ->
                val sql = """
                    DELETE FROM OrderLogs
                    WHERE consumed_at < DATEADD(DAY, -?, GETDATE())
                """.trimIndent()

                conn.prepareStatement(sql).use { stmt ->
                    stmt.setInt(1, retentionDays)
                    val deletedCount = stmt.executeUpdate()

                    if (deletedCount > 0) {
                        logger.info("Cleaned up $deletedCount old records (older than $retentionDays days)")
                    } else {
                        logger.debug("No old records to clean up")
                    }

                    deletedCount
                }
            }
        } catch (e: Exception) {
            logger.error("Failed to cleanup old records", e)
            0
        }
    }

    fun cleanupAllRecords(): Int {
        return try {
            DatabaseConfig.getConnection().use { conn ->
                val sql = "TRUNCATE TABLE OrderLogs"
                conn.createStatement().use { stmt ->
                    stmt.execute(sql)
                    logger.info("Truncated OrderLogs table (all records deleted)")
                }

                // Get count that was deleted
                val countSql = "SELECT COUNT(*) as cnt FROM OrderLogs"
                conn.createStatement().use { stmt ->
                    val rs = stmt.executeQuery(countSql)
                    if (rs.next()) rs.getInt("cnt") else 0
                }
            }
        } catch (e: Exception) {
            logger.error("Failed to truncate OrderLogs", e)
            0
        }
    }

    fun stop() {
        logger.info("Stopping database cleanup scheduler")
        scheduler.shutdown()
        try {
            if (!scheduler.awaitTermination(5, TimeUnit.SECONDS)) {
                scheduler.shutdownNow()
            }
        } catch (e: InterruptedException) {
            scheduler.shutdownNow()
        }
    }
}
