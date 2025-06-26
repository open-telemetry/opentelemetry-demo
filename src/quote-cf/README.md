# Quote Service - ColdFusion Implementation

The Quote Service is a ColdFusion-based microservice that provides quote generation and management functionality for the OpenTelemetry Demo application. It demonstrates real-world ColdFusion application patterns, database integration, and observability features.

## Overview

This service generates quotes for customers based on available services, manages quote lifecycle, and provides various endpoints for quote operations. It's built using Adobe ColdFusion/Lucee and integrates with SQLite for data persistence.

## Features

- **Quote Generation**: Creates detailed quotes with customer information, services, and pricing
- **Database Integration**: Full SQLite integration with complex queries and transactions
- **Email Processing**: Quote email functionality with error simulation
- **Quote Management**: Update, retrieve, and cleanup operations
- **Performance Testing**: Includes deliberately slow queries for observability testing
- **Error Simulation**: Built-in error conditions for testing resilience

## Endpoints

### Core Quote Operations

- `GET /getquote.cfm` - Generate a new quote (POST with JSON payload)
- `GET /emailquote.cfm` - Process quote for email delivery
- `GET /updatequote.cfm` - Update existing quote information
- `GET /removeoldquotes.cfm` - Cleanup old quotes (may include slow queries)
- `GET /report.cfm` - Generates a fake OutOfMemory Error

### Additional Endpoints

- `GET /index.cfm` - Service health check
- `GET /debug.cfm` - Debug information and diagnostics


## Database Schema

The service uses a SQLite database with the following tables:

- **customers** - Customer information and contact details
- **services** - Available services with pricing and categories
- **quotes** - Quote headers with totals and status
- **quote_items** - Individual line items for each quote

### Sample Data

The database includes sample data:
- 10 active customers from various industries
- 15 services across Technology, Consulting, Analytics, and other categories
- Pre-generated quotes with realistic pricing and relationships

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SQLITE_DB_PATH` | `/data/quotes.db` | SQLite database file path |
| `LUCEE_REQUEST_TIMEOUT` | `600` | Request timeout in seconds |

### SQLite Configuration

The application is configured to use SQLite JDBC driver with the following settings:

- **Driver Class**: `org.sqlite.JDBC`
- **Bundle**: `org.xerial.sqlite-jdbc` (version 3.36.0.3)
- **Connection String**: `jdbc:sqlite:/data/quotes.db`
- **Database File**: Mounted from host `./src/sql/quotes.db` to container `/data/quotes.db`

The SQLite database file contains pre-populated sample data and is automatically created from the SQL schema if it doesn't exist.