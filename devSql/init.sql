-- Create databases
CREATE DATABASE currency_db;
CREATE DATABASE quote_db;
CREATE DATABASE product_catalog_db;
CREATE DATABASE email_db;

-- Create users and grant privileges

-- User for currency_db
CREATE USER currency_service WITH PASSWORD 'currency';
GRANT CONNECT ON DATABASE currency_db TO currency_service;
GRANT ALL PRIVILEGES ON DATABASE currency_db TO currency_service;

-- User for quote_db
CREATE USER quote_service WITH PASSWORD 'quote';
GRANT CONNECT ON DATABASE quote_db TO quote_service;
GRANT ALL PRIVILEGES ON DATABASE quote_db TO quote_service;

-- User for product_catalog_db
CREATE USER product_catalog_service WITH PASSWORD 'product_catalog';
GRANT CONNECT ON DATABASE product_catalog_db TO product_catalog_service;
GRANT ALL PRIVILEGES ON DATABASE product_catalog_db TO product_catalog_service;

-- User for email_db
CREATE USER email_service WITH PASSWORD 'email';
GRANT CONNECT ON DATABASE email_db TO email_service;
GRANT ALL PRIVILEGES ON DATABASE email_db TO email_service;

-- Connect to currency_db and create tables
\c currency_db;

-- Create tables in currency_db
CREATE TABLE IF NOT EXISTS currencies (
    id SERIAL PRIMARY KEY,
    currency_code VARCHAR(3) UNIQUE NOT NULL,
    currency_name VARCHAR(50) NOT NULL
);

CREATE TABLE IF NOT EXISTS exchange_rates (
    id SERIAL PRIMARY KEY,
    currency_from VARCHAR(3) NOT NULL,
    currency_to VARCHAR(3) NOT NULL,
    rate NUMERIC(10, 6) NOT NULL,
    last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (currency_from) REFERENCES currencies(currency_code),
    FOREIGN KEY (currency_to) REFERENCES currencies(currency_code)
);