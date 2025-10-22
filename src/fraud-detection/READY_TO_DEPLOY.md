# Ready to Deploy: Fraud Detection with SQL Server Logging

## Build Status: ✅ SUCCESS

**Image Built and Pushed:**
```
ghcr.io/splunk/opentelemetry-demo/otel-fraud-detection:2.1.3-sql.1
```

**Digest:**
```
sha256:d000660e4ae80649d431a7ba03557287bc82dae93c862f0b9eccef14ab61450e
```

## What's Included in This Build

### Code Changes
1. **SQL Server JDBC Driver** - Microsoft SQL Server JDBC 12.8.1
2. **HikariCP Connection Pool** - Enterprise-grade connection pooling
3. **Protobuf JSON Utilities** - For converting OrderResult to JSON
4. **Database Auto-Creation** - Automatically creates database and tables on startup
5. **Kafka Message Logging** - Every order consumed is logged to SQL Server

### Configuration Updates
- **Image Version**: Updated to `2.1.3-sql.1` in `kubernetes/opentelemetry-demo.yaml`
- **SQL Server Host**: `sql-express.sql.svc.cluster.local`
- **Password**: `ChangeMe_SuperStrong123!` (hardcoded for testing)
- **Init Container**: Added wait-for-sqlserver to ensure DB is ready

## Deployment Commands

### Quick Deploy (Apply Everything)
```bash
cd /Users/phagen/GIT/opentelemetry-demo-Splunk

# Apply the entire manifest (includes existing SQL Server)
kubectl apply -f kubernetes/opentelemetry-demo.yaml
```

### Targeted Deploy (Fraud Detection Only)
```bash
# If SQL Server is already running, just update fraud-detection
kubectl rollout restart deployment/fraud-detection -n otel-demo

# Or delete and recreate
kubectl delete deployment fraud-detection -n otel-demo
kubectl apply -f kubernetes/opentelemetry-demo.yaml
```

## Verification Steps

### 1. Check Pod Status
```bash
# Check fraud-detection is running
kubectl get pods -n otel-demo -l app.kubernetes.io/component=fraud-detection

# Expected output:
# NAME                                READY   STATUS    RESTARTS   AGE
# fraud-detection-xxxxxxxxxx-xxxxx    1/1     Running   0          1m
```

### 2. Watch Logs
```bash
# Follow fraud-detection logs
kubectl logs -f -n otel-demo -l app.kubernetes.io/component=fraud-detection

# Look for these SUCCESS indicators:
# ✓ "Database initialized successfully"
# ✓ "OrderLogs table verified/created successfully"
# ✓ "Consumed record with orderId: <id>"
# ✓ "Order <id> logged to database"
```

### 3. Check SQL Server Connection
```bash
# Verify SQL Server is running in sql namespace
kubectl get pods -n sql -l app=sql-express

# Port-forward to access SQL Server
kubectl port-forward -n sql svc/sql-express 1433:1433
```

### 4. Query the Database
```bash
# Connect using sqlcmd
kubectl exec -it sql-express-0 -n sql -- /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P 'ChangeMe_SuperStrong123!'
```

Run in sqlcmd:
```sql
-- Check database exists
SELECT name FROM sys.databases;
GO

-- Use the database
USE FraudDetection;
GO

-- Count orders
SELECT COUNT(*) as total_orders FROM OrderLogs;
GO

-- View recent orders
SELECT TOP 5
    order_id,
    shipping_city,
    shipping_country,
    items_count,
    consumed_at
FROM OrderLogs
ORDER BY consumed_at DESC;
GO
```

## What Happens When You Deploy

1. **Init Container Phase**
   - `wait-for-kafka` waits for Kafka to be ready (port 9092)
   - `wait-for-sqlserver` waits for SQL Server to be ready (port 1433)

2. **Startup Phase**
   - Fraud-detection connects to SQL Server at `sql-express.sql.svc.cluster.local:1433`
   - Creates `FraudDetection` database if it doesn't exist
   - Creates `OrderLogs` table with proper schema and indexes
   - Initializes HikariCP connection pool (2-10 connections)
   - Connects to Kafka and subscribes to `orders` topic

3. **Runtime Phase**
   - Consumes messages from Kafka every 100ms
   - Parses OrderResult protobuf messages
   - Logs each order to database with full details
   - Converts order items to JSON for storage
   - Records consumption timestamp

## Database Schema Created

```sql
CREATE TABLE OrderLogs (
    id BIGINT IDENTITY(1,1) PRIMARY KEY,
    order_id NVARCHAR(255) NOT NULL,
    shipping_tracking_id NVARCHAR(255),
    shipping_cost_currency NVARCHAR(10),
    shipping_cost_units BIGINT,
    shipping_cost_nanos INT,
    shipping_street NVARCHAR(500),
    shipping_city NVARCHAR(255),
    shipping_state NVARCHAR(255),
    shipping_country NVARCHAR(255),
    shipping_zip NVARCHAR(50),
    items_count INT,
    items_json NVARCHAR(MAX),      -- Full order details as JSON
    consumed_at DATETIME2,          -- When message was consumed
    created_at DATETIME2
);

-- Indexes for performance
CREATE INDEX idx_order_id ON OrderLogs(order_id);
CREATE INDEX idx_consumed_at ON OrderLogs(consumed_at);
```

## Expected Logs

### Successful Startup
```
Database initialized successfully
OrderLogs table verified/created successfully
Consumed record with orderId: abc123, and updated total count to: 1
Order abc123 logged to database
```

### Feature Flag Handling
```
FeatureFlag 'kafkaQueueProblems' is enabled, sleeping 1 second
```

### Errors (if any)
```
Failed to initialize database
Failed to log order <id> to database
Exception while logging order <id> to database
```

## Troubleshooting

### Fraud Detection Crashes on Startup

**Check init container logs:**
```bash
kubectl logs -n otel-demo <pod-name> -c wait-for-sqlserver
kubectl logs -n otel-demo <pod-name> -c wait-for-kafka
```

**Check SQL Server is accessible:**
```bash
kubectl exec -it <fraud-pod> -n otel-demo -- nc -zv sql-express.sql.svc.cluster.local 1433
```

### Database Connection Errors

**Verify SQL Server password:**
```bash
kubectl get secret mssql-secrets -n sql -o jsonpath='{.data.SA_PASSWORD}' | base64 -d
# Should output: ChangeMe_SuperStrong123!
```

**Check SQL Server logs:**
```bash
kubectl logs -n sql sql-express-0
```

### No Orders Being Logged

**Verify Kafka is producing orders:**
```bash
# Check checkout service is creating orders
kubectl logs -n otel-demo -l app.kubernetes.io/component=checkout | grep -i order
```

**Check fraud-detection is consuming:**
```bash
kubectl logs -n otel-demo -l app.kubernetes.io/component=fraud-detection | grep "Consumed record"
```

**Check database writes:**
```bash
kubectl logs -n otel-demo -l app.kubernetes.io/component=fraud-detection | grep "logged to database"
```

## Next Steps After Deployment

1. **Generate Test Orders**
   - Access the demo frontend
   - Place some orders through the UI
   - Watch them appear in the database

2. **Query and Analyze**
   ```sql
   -- Orders by country
   SELECT shipping_country, COUNT(*) as count
   FROM OrderLogs
   GROUP BY shipping_country
   ORDER BY count DESC;

   -- High-value orders
   SELECT * FROM OrderLogs
   WHERE shipping_cost_units > 20
   ORDER BY consumed_at DESC;
   ```

3. **Add Fraud Detection Logic**
   - Implement scoring in `main.kt`
   - Flag suspicious patterns
   - Send alerts for fraud

4. **Create Dashboards**
   - Connect BI tools to SQL Server
   - Visualize order patterns
   - Monitor fraud trends

## Files Modified

### Code
- ✅ `src/fraud-detection/build.gradle.kts` - Added dependencies
- ✅ `src/fraud-detection/src/main/kotlin/frauddetection/DatabaseConfig.kt` - New file
- ✅ `src/fraud-detection/src/main/kotlin/frauddetection/OrderLogRepository.kt` - New file
- ✅ `src/fraud-detection/src/main/kotlin/frauddetection/main.kt` - Integrated DB logging

### Configuration
- ✅ `kubernetes/opentelemetry-demo.yaml` - Updated fraud-detection deployment

### Documentation
- ✅ `SQL_SERVER_SETUP.md` - Comprehensive setup guide
- ✅ `DEPLOYMENT_CHANGES.md` - Configuration changes
- ✅ `READY_TO_DEPLOY.md` - This file
- ✅ `sql/init-database.sql` - Manual DB initialization script

## Summary

Everything is ready to deploy! The fraud-detection service will now:
- ✅ Consume messages from Kafka `orders` topic
- ✅ Parse OrderResult protobuf messages
- ✅ Log every order to SQL Server with full details
- ✅ Store order items as JSON for easy querying
- ✅ Auto-create database and tables on startup
- ✅ Handle errors gracefully with logging

**Just run:**
```bash
kubectl apply -f kubernetes/opentelemetry-demo.yaml
```

And watch the logs to see orders being logged to the database!
