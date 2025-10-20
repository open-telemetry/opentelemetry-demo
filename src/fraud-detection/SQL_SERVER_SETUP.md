# SQL Server Integration for Fraud Detection Service

## Overview

The fraud-detection service now logs every Kafka message to a SQL Server database running in your Kubernetes cluster. Each order message consumed from the `orders` topic is persisted to the `OrderLogs` table with full order details.

## Architecture

```
Kafka (orders topic) → Fraud Detection Service → SQL Server (OrderLogs table)
```

## Database Schema

### OrderLogs Table

| Column | Type | Description |
|--------|------|-------------|
| id | BIGINT (PK) | Auto-increment primary key |
| order_id | NVARCHAR(255) | Order ID from Kafka message |
| shipping_tracking_id | NVARCHAR(255) | Shipping tracking number |
| shipping_cost_currency | NVARCHAR(10) | Currency code (e.g., USD) |
| shipping_cost_units | BIGINT | Whole units of shipping cost |
| shipping_cost_nanos | INT | Nano units of shipping cost |
| shipping_street | NVARCHAR(500) | Shipping street address |
| shipping_city | NVARCHAR(255) | Shipping city |
| shipping_state | NVARCHAR(255) | Shipping state |
| shipping_country | NVARCHAR(255) | Shipping country |
| shipping_zip | NVARCHAR(50) | Shipping ZIP code |
| items_count | INT | Number of items in order |
| items_json | NVARCHAR(MAX) | Full order JSON (protobuf → JSON) |
| consumed_at | DATETIME2 | Timestamp when message was consumed |
| created_at | DATETIME2 | Timestamp when record was created |

**Indexes:**
- `idx_order_id` on `order_id`
- `idx_consumed_at` on `consumed_at`
- `idx_shipping_country` on `shipping_country`
- `idx_created_at` on `created_at`

## Deployment Steps

### 1. Deploy SQL Server to Kubernetes

```bash
# Apply SQL Server deployment
kubectl apply -f src/fraud-detection/kubernetes/sqlserver-deployment.yaml

# Wait for SQL Server to be ready
kubectl wait --for=condition=ready pod -l app=sqlserver -n otel-demo --timeout=300s

# Check SQL Server pod status
kubectl get pods -n otel-demo -l app=sqlserver
```

### 2. Verify SQL Server Connection

```bash
# Get the SQL Server pod name
SQL_POD=$(kubectl get pods -n otel-demo -l app=sqlserver -o jsonpath='{.items[0].metadata.name}')

# Connect to SQL Server using sqlcmd
kubectl exec -it $SQL_POD -n otel-demo -- /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P 'YourStrong!Passw0rd'
```

Inside sqlcmd:
```sql
SELECT @@VERSION;
GO
```

### 3. (Optional) Initialize Database Manually

The fraud-detection service automatically creates the database and table on startup. However, you can initialize it manually if needed:

```bash
# Copy the SQL script to the pod
kubectl cp src/fraud-detection/sql/init-database.sql $SQL_POD:/tmp/init-database.sql -n otel-demo

# Execute the script
kubectl exec -it $SQL_POD -n otel-demo -- /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P 'YourStrong!Passw0rd' -i /tmp/init-database.sql
```

### 4. Build and Deploy Fraud Detection Service

```bash
# Build the new Docker image with SQL Server support
cd src/fraud-detection
./build-fraud-detection.sh

# Update the image in your Kubernetes deployment
# Edit kubernetes/opentelemetry-demo.yaml and update the fraud-detection image tag

# Apply the updated deployment (already contains SQL Server env vars)
kubectl apply -f ../../kubernetes/opentelemetry-demo.yaml

# Check fraud-detection pod logs
kubectl logs -f -n otel-demo -l app.kubernetes.io/component=fraud-detection
```

## Environment Variables

The following environment variables are configured in the fraud-detection deployment:

| Variable | Value | Description |
|----------|-------|-------------|
| SQL_SERVER_HOST | sqlserver | Kubernetes service name for SQL Server |
| SQL_SERVER_PORT | 1433 | SQL Server port |
| SQL_SERVER_DATABASE | FraudDetection | Database name |
| SQL_SERVER_USER | sa | SQL Server username |
| SQL_SERVER_PASSWORD | (from secret) | SQL Server password from sqlserver-secret |

## Configuration

### Change SQL Server Password

Edit the secret before deploying:

```bash
# Edit the password in kubernetes/sqlserver-deployment.yaml
# Or create a new secret:
kubectl create secret generic sqlserver-secret \
  --from-literal=password='YourNewStrongPassword123!' \
  -n otel-demo \
  --dry-run=client -o yaml | kubectl apply -f -
```

### Adjust SQL Server Resources

Edit `src/fraud-detection/kubernetes/sqlserver-deployment.yaml`:

```yaml
resources:
  requests:
    memory: "2Gi"
    cpu: "1000m"
  limits:
    memory: "4Gi"
    cpu: "2000m"
```

## Querying the Data

### Connect to SQL Server

```bash
# Port-forward to access SQL Server from your local machine
kubectl port-forward -n otel-demo svc/sqlserver 1433:1433

# Connect using any SQL Server client:
# - Azure Data Studio
# - SQL Server Management Studio (SSMS)
# - sqlcmd
# - DBeaver

# Connection details:
# Host: localhost
# Port: 1433
# Database: FraudDetection
# Username: sa
# Password: YourStrong!Passw0rd
```

### Example Queries

```sql
-- View most recent orders
SELECT TOP 10 * FROM OrderLogs ORDER BY consumed_at DESC;

-- Count orders by country
SELECT shipping_country, COUNT(*) as order_count
FROM OrderLogs
GROUP BY shipping_country
ORDER BY order_count DESC;

-- Find high-value orders (shipping cost > $20)
SELECT order_id, shipping_cost_units, shipping_country, consumed_at
FROM OrderLogs
WHERE shipping_cost_units >= 20
ORDER BY shipping_cost_units DESC;

-- Order volume by hour
SELECT
    DATEPART(HOUR, consumed_at) as hour,
    COUNT(*) as order_count
FROM OrderLogs
WHERE consumed_at >= DATEADD(DAY, -1, GETDATE())
GROUP BY DATEPART(HOUR, consumed_at)
ORDER BY hour;

-- View full order JSON details
SELECT
    order_id,
    items_count,
    JSON_VALUE(items_json, '$.orderId') as json_order_id,
    items_json,
    consumed_at
FROM OrderLogs
ORDER BY consumed_at DESC;
```

## Monitoring

### Check Fraud Detection Logs

```bash
# View logs to confirm database writes
kubectl logs -f -n otel-demo -l app.kubernetes.io/component=fraud-detection

# Look for these log messages:
# - "Database initialized successfully"
# - "Successfully saved order <order-id> to database"
# - "Order <order-id> logged to database"
```

### Monitor SQL Server

```bash
# Check SQL Server pod
kubectl get pods -n otel-demo -l app=sqlserver

# View SQL Server logs
kubectl logs -n otel-demo -l app=sqlserver

# Check SQL Server resource usage
kubectl top pod -n otel-demo -l app=sqlserver
```

## Troubleshooting

### Fraud Detection Can't Connect to SQL Server

1. Check SQL Server is running:
```bash
kubectl get pods -n otel-demo -l app=sqlserver
```

2. Verify secret exists:
```bash
kubectl get secret sqlserver-secret -n otel-demo
```

3. Check fraud-detection logs for connection errors:
```bash
kubectl logs -n otel-demo -l app.kubernetes.io/component=fraud-detection | grep -i "database\|sql"
```

### Database Table Not Created

The fraud-detection service auto-creates the table on startup. If it fails:

1. Manually create using the SQL script:
```bash
kubectl exec -it $SQL_POD -n otel-demo -- /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P 'YourStrong!Passw0rd' -Q "CREATE DATABASE FraudDetection"
```

2. Check database exists:
```bash
kubectl exec -it $SQL_POD -n otel-demo -- /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P 'YourStrong!Passw0rd' -Q "SELECT name FROM sys.databases"
```

### Performance Issues

If the database writes are slow:

1. Increase SQL Server resources in `sqlserver-deployment.yaml`
2. Add more database indexes
3. Consider using async writes or batching in the application
4. Check persistent volume performance

## Code Structure

### New Files Added

- `src/main/kotlin/frauddetection/DatabaseConfig.kt` - Database connection pooling with HikariCP
- `src/main/kotlin/frauddetection/OrderLogRepository.kt` - Repository for database operations
- `kubernetes/sqlserver-deployment.yaml` - K8s resources for SQL Server
- `sql/init-database.sql` - Database initialization script

### Modified Files

- `build.gradle.kts` - Added SQL Server JDBC and HikariCP dependencies
- `src/main/kotlin/frauddetection/main.kt` - Integrated database logging in Kafka consumer
- `../../kubernetes/opentelemetry-demo.yaml` - Added SQL Server environment variables to fraud-detection

## Next Steps

### Fraud Detection Features to Add

1. **Fraud Scoring**: Analyze orders and calculate fraud probability
2. **Alerting**: Send alerts when suspicious orders detected
3. **Dashboard**: Create visualization of fraud patterns
4. **ML Integration**: Train models on historical order data
5. **Real-time Actions**: Block/hold suspicious orders automatically

### Example Fraud Detection Logic

```kotlin
fun calculateFraudScore(order: OrderResult): Double {
    var score = 0.0

    // High-value order
    if (order.shippingCost.units > 100) score += 0.3

    // Multiple items
    if (order.itemsCount > 10) score += 0.2

    // International shipping to high-risk countries
    val highRiskCountries = listOf("XX", "YY") // Add actual countries
    if (order.shippingAddress.country in highRiskCountries) score += 0.4

    // Add more rules...

    return score
}
```

## References

- [SQL Server on Kubernetes](https://learn.microsoft.com/en-us/sql/linux/sql-server-linux-kubernetes-deploy)
- [HikariCP Documentation](https://github.com/brettwooldridge/HikariCP)
- [Microsoft JDBC Driver for SQL Server](https://learn.microsoft.com/en-us/sql/connect/jdbc/microsoft-jdbc-driver-for-sql-server)
