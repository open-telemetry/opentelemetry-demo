# Quote Service - ColdFusion Implementation

The Quote Service is a ColdFusion-based microservice that provides quote generation and management functionality for the OpenTelemetry Demo application. It demonstrates real-world ColdFusion application patterns, database integration, and observability features.

## Overview

This service generates quotes for customers based on available services, manages quote lifecycle, and provides various endpoints for quote operations. It's built using Adobe ColdFusion/Lucee and integrates with MySQL for data persistence.

## Features

- **Quote Generation**: Creates detailed quotes with customer information, services, and pricing
- **Database Integration**: Full MySQL integration with complex queries and transactions
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

The service uses a MySQL database with the following tables:

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
| `MYSQL_HOST` | `mysql-quote` | MySQL database host |
| `MYSQL_PORT` | `3306` | MySQL database port |
| `MYSQL_DATABASE` | `quotes` | Database name |
| `MYSQL_USER` | `root` | Database username |
| `MYSQL_PASSWORD` | `password` | Database password |
| `LUCEE_REQUEST_TIMEOUT` | `600` | Request timeout in seconds |