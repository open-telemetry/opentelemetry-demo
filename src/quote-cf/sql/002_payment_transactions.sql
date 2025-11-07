-- Payment transactions table for Payment Service
-- This table stores all payment transaction attempts for audit and observability

CREATE TABLE IF NOT EXISTS payment_transactions (
  transaction_id VARCHAR(36) PRIMARY KEY,
  card_type VARCHAR(20) NOT NULL,
  last_four_digits VARCHAR(4) NOT NULL,
  amount_units BIGINT NOT NULL,
  amount_nanos INT NOT NULL DEFAULT 0,
  currency_code VARCHAR(3) NOT NULL,
  loyalty_level VARCHAR(20) DEFAULT NULL,
  charged BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_created_at (created_at),
  INDEX idx_card_type (card_type),
  INDEX idx_charged (charged)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
