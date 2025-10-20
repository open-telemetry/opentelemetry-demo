-- SQL Server Database Initialization Script
-- This script creates the FraudDetection database and OrderLogs table
-- Note: The table is also auto-created by the fraud-detection service on startup

-- Create database if it doesn't exist
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'FraudDetection')
BEGIN
    CREATE DATABASE FraudDetection;
END
GO

USE FraudDetection;
GO

-- Create OrderLogs table
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

    -- Create indexes for better query performance
    CREATE INDEX idx_order_id ON OrderLogs(order_id);
    CREATE INDEX idx_consumed_at ON OrderLogs(consumed_at);
    CREATE INDEX idx_shipping_country ON OrderLogs(shipping_country);
    CREATE INDEX idx_created_at ON OrderLogs(created_at);
END
GO

-- Verify table creation
SELECT
    'OrderLogs table created successfully' AS Status,
    COUNT(*) AS RecordCount
FROM OrderLogs;
GO

-- Example queries to use after data is populated:

-- Query 1: View most recent orders
-- SELECT TOP 10 * FROM OrderLogs ORDER BY consumed_at DESC;

-- Query 2: Orders by country
-- SELECT shipping_country, COUNT(*) as order_count
-- FROM OrderLogs
-- GROUP BY shipping_country
-- ORDER BY order_count DESC;

-- Query 3: Orders with high shipping costs (over $20)
-- SELECT order_id, shipping_cost_currency, shipping_cost_units, shipping_street, shipping_city, shipping_country
-- FROM OrderLogs
-- WHERE shipping_cost_units >= 20
-- ORDER BY shipping_cost_units DESC;

-- Query 4: Order volume by hour
-- SELECT
--     DATEPART(HOUR, consumed_at) as hour,
--     COUNT(*) as order_count
-- FROM OrderLogs
-- WHERE consumed_at >= DATEADD(DAY, -1, GETDATE())
-- GROUP BY DATEPART(HOUR, consumed_at)
-- ORDER BY hour;

-- Query 5: View full order details with JSON
-- SELECT
--     order_id,
--     shipping_tracking_id,
--     items_count,
--     items_json,
--     consumed_at
-- FROM OrderLogs
-- ORDER BY consumed_at DESC;
