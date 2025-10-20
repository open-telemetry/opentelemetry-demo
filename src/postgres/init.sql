-- Copyright The OpenTelemetry Authors
-- SPDX-License-Identifier: Apache-2.0

-- Create the shop_db database if it does not exist (uses psql \gexec)
SELECT 'CREATE DATABASE shop_db' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'shop_db')\gexec

-- Create shop_user (idempotent)
DO
$$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'shop_user') THEN
    CREATE ROLE shop_user LOGIN PASSWORD 'shop_password';
  END IF;
END
$$;

-- Ensure monitoring_user exists (idempotent)
DO
$$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'monitoring_user') THEN
    CREATE ROLE monitoring_user LOGIN PASSWORD 'monitoring_password';
  END IF;
END
$$;

-- Give connect privileges on the database to the users
GRANT CONNECT ON DATABASE shop_db TO shop_user;
GRANT CONNECT ON DATABASE shop_db TO monitoring_user;

-- Switch to the shop_db database to create tables and grant schema/table privileges
\connect shop_db

-- Create tables inside shop_db (idempotent)
CREATE TABLE IF NOT EXISTS "order" (
    order_id TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS shipping (
    shipping_tracking_id TEXT PRIMARY KEY,
    shipping_cost_currency_code TEXT NOT NULL,
    shipping_cost_units BIGINT NOT NULL,
    shipping_cost_nanos INT NOT NULL,
    street_address TEXT,
    city TEXT,
    state TEXT,
    country TEXT,
    zip_code TEXT,
    order_id TEXT NOT NULL,
    FOREIGN KEY (order_id) REFERENCES "order"(order_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS orderitem (
    item_cost_currency_code TEXT NOT NULL,
    item_cost_units BIGINT NOT NULL,
    item_cost_nanos INT NOT NULL,
    product_id TEXT NOT NULL,
    quantity INT NOT NULL,
    order_id TEXT NOT NULL,
    PRIMARY KEY (order_id, product_id),
    FOREIGN KEY (order_id) REFERENCES "order"(order_id) ON DELETE CASCADE
);

-- Grant read/write privileges on existing and future tables to shop_user
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO shop_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE ON TABLES TO shop_user;

-- Grant monitoring privileges to monitoring_user
GRANT pg_monitor TO monitoring_user;
GRANT USAGE ON SCHEMA public TO monitoring_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO monitoring_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO monitoring_user;

