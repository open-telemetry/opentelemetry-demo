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

-- Extra indexes slow down INSERTs and UPDATEs (especially status changes)
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_shop_transactions_customer_status_created' AND object_id = OBJECT_ID('shop_transactions'))
CREATE INDEX idx_shop_transactions_customer_status_created ON shop_transactions(customer_email, status, created_at);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_shop_transactions_store_terminal' AND object_id = OBJECT_ID('shop_transactions'))
CREATE INDEX idx_shop_transactions_store_terminal ON shop_transactions(store_location, terminal_id);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_shop_transactions_status_store' AND object_id = OBJECT_ID('shop_transactions'))
CREATE INDEX idx_shop_transactions_status_store ON shop_transactions(status, store_location, created_at);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_shop_transactions_status_customer' AND object_id = OBJECT_ID('shop_transactions'))
CREATE INDEX idx_shop_transactions_status_customer ON shop_transactions(status, customer_email, total_amount);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_shop_transactions_status_amount' AND object_id = OBJECT_ID('shop_transactions'))
CREATE INDEX idx_shop_transactions_status_amount ON shop_transactions(status, total_amount, processed_at);

-- Check constraint that runs expensive queries on every INSERT
IF NOT EXISTS (SELECT * FROM sys.check_constraints WHERE name = 'chk_shop_transactions_validation')
ALTER TABLE shop_transactions
ADD CONSTRAINT chk_shop_transactions_validation
CHECK (
    (SELECT COUNT(*) FROM shop_transactions st 
     WHERE LOWER(st.customer_email) LIKE '%' + LOWER(customer_email) + '%') >= 0
    AND (SELECT COUNT(*) FROM shop_transactions st 
         WHERE REPLACE(st.store_location, ' ', '') = REPLACE(store_location, ' ', '')) >= 0
    AND (SELECT AVG(CAST(total_amount AS FLOAT)) 
         FROM shop_transactions 
         WHERE store_location = store_location) >= 0
    OR total_amount >= 0
);

-- Audit table for tracking changes
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='shop_transaction_audit' and xtype='U')
CREATE TABLE shop_transaction_audit (
    audit_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    transaction_id NVARCHAR(255),
    old_status NVARCHAR(20),
    new_status NVARCHAR(20),
    customer_count INT,
    store_avg_amount DECIMAL(10,2),
    updated_at DATETIME2 DEFAULT GETDATE()
);

-- Trigger on UPDATE that runs expensive queries
IF OBJECT_ID('trg_shop_transactions_update', 'TR') IS NOT NULL
DROP TRIGGER trg_shop_transactions_update;
GO

CREATE TRIGGER trg_shop_transactions_update
ON shop_transactions
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Expensive audit queries on every UPDATE
    INSERT INTO shop_transaction_audit (transaction_id, old_status, new_status, customer_count, store_avg_amount)
    SELECT 
        i.transaction_id,
        d.status,
        i.status,
        (SELECT COUNT(*) FROM shop_transactions t1 
         CROSS JOIN shop_transactions t2 
         WHERE t1.customer_email = i.customer_email),
        (SELECT AVG(CAST(t3.total_amount AS FLOAT)) 
         FROM shop_transactions t3 
         WHERE LOWER(t3.store_location) LIKE LOWER('%' + i.store_location + '%'))
    FROM inserted i
    INNER JOIN deleted d ON i.id = d.id;
END;
GO