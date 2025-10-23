-- Copyright The OpenTelemetry Authors
-- SPDX-License-Identifier: Apache-2.0

-- Database schema for shop datacenter shim service (SQL Server)

-- Create main transactions table
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='shop_transactions' and xtype='U')
CREATE TABLE shop_transactions (
    id BIGINT IDENTITY(1,1) PRIMARY KEY,
    transaction_id NVARCHAR(255) UNIQUE NOT NULL,
    local_order_id NVARCHAR(255) NOT NULL,
    cloud_order_id NVARCHAR(255),
    customer_email NVARCHAR(255) NOT NULL,
    customer_name NVARCHAR(255),
    total_amount DECIMAL(10,2),
    currency_code NCHAR(3),
    status NVARCHAR(20) NOT NULL DEFAULT 'INITIATED',
    store_location NVARCHAR(100),
    terminal_id NVARCHAR(50),
    created_at DATETIME2 DEFAULT GETDATE(),
    processed_at DATETIME2,
    cloud_submitted_at DATETIME2,
    cloud_confirmed_at DATETIME2,
    error_message NTEXT,
    retry_count INT DEFAULT 0,
    shipping_address NTEXT,
    items_json NTEXT
);

-- Indexes for better performance
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_shop_transactions_transaction_id' AND object_id = OBJECT_ID('shop_transactions'))
CREATE INDEX idx_shop_transactions_transaction_id ON shop_transactions(transaction_id);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_shop_transactions_local_order_id' AND object_id = OBJECT_ID('shop_transactions'))
CREATE INDEX idx_shop_transactions_local_order_id ON shop_transactions(local_order_id);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_shop_transactions_cloud_order_id' AND object_id = OBJECT_ID('shop_transactions'))
CREATE INDEX idx_shop_transactions_cloud_order_id ON shop_transactions(cloud_order_id);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_shop_transactions_status' AND object_id = OBJECT_ID('shop_transactions'))
CREATE INDEX idx_shop_transactions_status ON shop_transactions(status);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_shop_transactions_created_at' AND object_id = OBJECT_ID('shop_transactions'))
CREATE INDEX idx_shop_transactions_created_at ON shop_transactions(created_at);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_shop_transactions_store_location' AND object_id = OBJECT_ID('shop_transactions'))
CREATE INDEX idx_shop_transactions_store_location ON shop_transactions(store_location);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_shop_transactions_customer_email' AND object_id = OBJECT_ID('shop_transactions'))
CREATE INDEX idx_shop_transactions_customer_email ON shop_transactions(customer_email);

-- Store location lookup table (for demo purposes)
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='store_locations' and xtype='U')
CREATE TABLE store_locations (
    id INT IDENTITY(1,1) PRIMARY KEY,
    store_code NVARCHAR(10) UNIQUE NOT NULL,
    store_name NVARCHAR(100) NOT NULL,
    address NTEXT,
    city NVARCHAR(50),
    state NVARCHAR(50),
    country NVARCHAR(50),
    timezone NVARCHAR(50) DEFAULT 'America/New_York',
    is_active BIT DEFAULT 1,
    created_at DATETIME2 DEFAULT GETDATE()
);

-- Insert sample store locations for demo (using MERGE to handle duplicates)
MERGE INTO store_locations AS target
USING (VALUES
    ('DC-NYC-01', 'Manhattan Flagship Store', '123 Broadway', 'New York', 'NY', 'USA'),
    ('DC-NYC-02', 'Brooklyn Heights Store', '456 Atlantic Ave', 'Brooklyn', 'NY', 'USA'),
    ('DC-BOS-01', 'Boston Downtown Store', '789 Washington St', 'Boston', 'MA', 'USA'),
    ('DC-PHI-01', 'Philadelphia Center Store', '321 Market St', 'Philadelphia', 'PA', 'USA'),
    ('DC-DC-01', 'Washington DC Capitol Store', '654 K Street NW', 'Washington', 'DC', 'USA')
) AS source (store_code, store_name, address, city, state, country)
ON target.store_code = source.store_code
WHEN NOT MATCHED THEN
    INSERT (store_code, store_name, address, city, state, country)
    VALUES (source.store_code, source.store_name, source.address, source.city, source.state, source.country);