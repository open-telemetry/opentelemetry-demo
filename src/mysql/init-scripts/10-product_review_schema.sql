-- Copyright The OpenTelemetry Authors
-- SPDX-License-Identifier: Apache-2.0

-- Create a new database
CREATE DATABASE IF NOT EXISTS reviews;

-- Switch to the new database
USE reviews;

CREATE USER 'otelu'@'%' IDENTIFIED BY 'otelp';

CREATE TABLE IF NOT EXISTS productreviews (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id VARCHAR(16) NOT NULL,
    username VARCHAR(64) NOT NULL,
    description VARCHAR(1024),
    score DECIMAL(2,1) NOT NULL
);

ALTER TABLE productreviews ADD INDEX product_id_index (product_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON reviews.productreviews TO 'otelu'@'%';

FLUSH PRIVILEGES;