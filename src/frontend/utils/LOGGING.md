# Splunk JSON Logger

The frontend service uses a custom JSON logger optimized for Splunk ingestion.

## Usage

```javascript
const { logger } = require('./utils/logger');

// Basic logging
logger.info('User action completed');
logger.warn('Cache miss detected');
logger.error('Failed to fetch data');

// Logging with additional fields
logger.info('Order placed', {
  orderId: '12345',
  userId: 'user-abc',
  total: 99.99,
});

// Error logging with stack trace
try {
  // some code
} catch (error) {
  logger.error('Payment processing failed', {
    error,
    orderId: '12345',
  });
}
```

## Log Format

All logs are output as single-line JSON with the following fields:

```json
{
  "timestamp": "2025-11-11T13:45:30.123Z",
  "level": "INFO",
  "service.name": "frontend",
  "message": "User action completed",
  "trace.id": "a1b2c3d4e5f6g7h8i9j0",
  "span.id": "1234567890abcdef",
  "trace.flags": "01"
}
```

## Key Features

- **Single-line JSON**: Each log is a single JSON object on one line
- **Trace correlation**: Automatically includes OpenTelemetry trace and span IDs
- **Splunk-optimized**: Field names follow Splunk conventions
- **ISO timestamps**: Standard ISO 8601 format
- **Custom fields**: Add any additional fields as needed

## Log Levels

- `logger.debug()` - Debug information
- `logger.info()` - Informational messages
- `logger.warn()` - Warning messages
- `logger.error()` - Error messages

## Splunk Queries

Example Splunk queries for this log format:

```spl
# Find all errors
index=* service.name=frontend level=ERROR

# Trace correlation
index=* trace.id="a1b2c3d4e5f6g7h8i9j0"

# Search by custom fields
index=* service.name=frontend orderId="12345"
```
