/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */

package frauddetection

import com.zaxxer.hikari.HikariConfig
import com.zaxxer.hikari.HikariDataSource
import org.apache.logging.log4j.LogManager
import org.apache.logging.log4j.Logger
import java.sql.Connection
import javax.sql.DataSource

object DatabaseConfig {
    private val logger: Logger = LogManager.getLogger(DatabaseConfig::class.java)

    private lateinit var dataSource: HikariDataSource

    fun initialize() {
        val host = System.getenv("SQL_SERVER_HOST") ?: "localhost"
        val port = System.getenv("SQL_SERVER_PORT") ?: "1433"
        val database = System.getenv("SQL_SERVER_DATABASE") ?: "FraudDetection"
        val username = System.getenv("SQL_SERVER_USER") ?: "sa"
        val password = System.getenv("SQL_SERVER_PASSWORD") ?: throw IllegalStateException("SQL_SERVER_PASSWORD is required")

        // First, connect to master database to create the FraudDetection database if needed
        createDatabaseIfNotExists(host, port, database, username, password)

        // Now connect to the FraudDetection database
        val jdbcUrl = "jdbc:sqlserver://$host:$port;databaseName=$database;encrypt=false;trustServerCertificate=true"

        val config = HikariConfig().apply {
            this.jdbcUrl = jdbcUrl
            this.username = username
            this.password = password
            this.driverClassName = "com.microsoft.sqlserver.jdbc.SQLServerDriver"
            maximumPoolSize = 10
            minimumIdle = 2
            connectionTimeout = 30000
            idleTimeout = 600000
            maxLifetime = 1800000
        }

        dataSource = HikariDataSource(config)
        logger.info("Database connection pool initialized: $jdbcUrl")

        // Create table if it doesn't exist
        createTableIfNotExists()
    }

    private fun createDatabaseIfNotExists(host: String, port: String, database: String, username: String, password: String) {
        // Connect to master database
        val masterUrl = "jdbc:sqlserver://$host:$port;databaseName=master;encrypt=false;trustServerCertificate=true"

        try {
            java.sql.DriverManager.getConnection(masterUrl, username, password).use { conn ->
                val statement = conn.createStatement()

                // Check if database exists
                val checkDbSQL = "SELECT database_id FROM sys.databases WHERE name = '$database'"
                val resultSet = statement.executeQuery(checkDbSQL)

                if (!resultSet.next()) {
                    // Database doesn't exist, create it
                    logger.info("Database '$database' does not exist. Creating...")
                    val createDbSQL = "CREATE DATABASE [$database]"
                    statement.execute(createDbSQL)
                    logger.info("Database '$database' created successfully")
                } else {
                    logger.info("Database '$database' already exists")
                }
            }
        } catch (e: Exception) {
            logger.error("Failed to create database '$database'", e)
            throw e
        }
    }

    fun getConnection(): Connection {
        return dataSource.connection
    }

    fun close() {
        if (::dataSource.isInitialized && !dataSource.isClosed) {
            dataSource.close()
            logger.info("Database connection pool closed")
        }
    }

    private fun createTableIfNotExists() {
        getConnection().use { conn ->
            val statement = conn.createStatement()

            // Create OrderLogs table
            val createOrderLogsSQL = """
                IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'OrderLogs')
                BEGIN
                    CREATE TABLE OrderLogs (
                        id BIGINT IDENTITY(1,1) PRIMARY KEY,
                        order_id NVARCHAR(255) NOT NULL,
                        shipping_tracking_id NVARCHAR(255),
                        shipping_cost_currency NVARCHAR(10),
                        shipping_cost_units BIGINT,
                        shipping_cost_nanos INT,
                        shipping_street NVARCHAR(500),
                        shipping_city NVARCHAR(255),
                        shipping_state NVARCHAR(255),
                        shipping_country NVARCHAR(255),
                        shipping_zip NVARCHAR(50),
                        items_count INT,
                        items_json NVARCHAR(MAX),
                        consumed_at DATETIME2 DEFAULT GETDATE(),
                        created_at DATETIME2 DEFAULT GETDATE()
                    );
                    CREATE INDEX idx_order_id ON OrderLogs(order_id);
                    CREATE INDEX idx_consumed_at ON OrderLogs(consumed_at);
                END
            """.trimIndent()

            statement.execute(createOrderLogsSQL)
            logger.info("OrderLogs table verified/created successfully")

            // Create FraudAlerts table
            val createFraudAlertsSQL = """
                IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'FraudAlerts')
                BEGIN
                    CREATE TABLE FraudAlerts (
                        id BIGINT IDENTITY(1,1) PRIMARY KEY,
                        order_id NVARCHAR(255) NOT NULL,
                        alert_type NVARCHAR(50) NOT NULL,
                        severity NVARCHAR(20) NOT NULL,
                        reason NVARCHAR(MAX),
                        risk_score FLOAT NOT NULL,
                        detected_at DATETIME2 DEFAULT GETDATE(),
                        created_at DATETIME2 DEFAULT GETDATE()
                    );
                    CREATE INDEX idx_fraud_order_id ON FraudAlerts(order_id);
                    CREATE INDEX idx_fraud_detected_at ON FraudAlerts(detected_at);
                    CREATE INDEX idx_fraud_severity ON FraudAlerts(severity);
                    CREATE INDEX idx_fraud_risk_score ON FraudAlerts(risk_score);
                END
            """.trimIndent()

            statement.execute(createFraudAlertsSQL)
            logger.info("FraudAlerts table verified/created successfully")
        }
    }
}
