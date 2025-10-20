# Fraud Detection SQL Server Integration - Deployment Changes

## Summary

The fraud-detection service has been updated to log all Kafka messages to the **existing SQL Server Express** deployment in your Kubernetes cluster.

## Key Findings

Your `opentelemetry-demo.yaml` already contains a SQL Server Express deployment (lines 303-400):
- **Namespace**: `sql`
- **Service Name**: `sql-express.sql.svc.cluster.local`
- **Secret Name**: `mssql-secrets`
- **Password**: `ChangeMe_SuperStrong123!` (exposed in secret for testing)
- **Resources**: 1Gi-2Gi memory, 250m-1 CPU
- **Storage**: 5Gi PVC via StatefulSet

## Changes Made to opentelemetry-demo.yaml

### 1. Fraud Detection Environment Variables (lines 1402-1411)

**Updated:**
```yaml
- name: SQL_SERVER_HOST
  value: sql-express.sql.svc.cluster.local  # Changed from 'sqlserver'
- name: SQL_SERVER_PORT
  value: "1433"
- name: SQL_SERVER_DATABASE
  value: FraudDetection                      # Will be auto-created
- name: SQL_SERVER_USER
  value: sa
- name: SQL_SERVER_PASSWORD
  value: "ChangeMe_SuperStrong123!"          # Hardcoded for testing (matches existing SQL server)
```

**Why:**
- Uses the existing SQL Server Express service instead of creating a new one
- Password matches the existing `mssql-secrets` secret value
- Hardcoded password for testing (you mentioned this is OK)

### 2. Init Container Added (lines 1423-1428)

**Added:**
```yaml
- command:
  - sh
  - -c
  - until nc -z -v -w30 sql-express.sql.svc.cluster.local 1433; do echo waiting for sql-express; sleep 2; done;
  image: busybox:latest
  name: wait-for-sqlserver
```

**Why:**
- Ensures SQL Server is ready before fraud-detection starts
- Prevents connection failures on startup
- Matches the pattern used for Kafka init container

## No Additional SQL Server Deployment Needed

**You do NOT need to apply the separate sqlserver-deployment.yaml file** I created earlier. The existing SQL Server Express in the main manifest is sufficient.

## What Happens on Deployment

1. **SQL Server Express** (already exists)
   - Running in `sql` namespace
   - Service accessible at `sql-express.sql.svc.cluster.local:1433`

2. **Fraud Detection** (updated)
   - Init container waits for SQL Server to be ready
   - On startup, connects to SQL Server
   - Auto-creates `FraudDetection` database if it doesn't exist
   - Auto-creates `OrderLogs` table with proper schema and indexes
   - Begins consuming from Kafka and logging to database

## Deployment Steps

### 1. Build the Updated Fraud Detection Image

```bash
cd /Users/phagen/GIT/opentelemetry-demo-Splunk/src/fraud-detection
./build-fraud-detection.sh

# Tag with your registry if needed
docker tag fraud-detection:latest YOUR_REGISTRY/fraud-detection:VERSION
docker push YOUR_REGISTRY/fraud-detection:VERSION
```

### 2. Update Image Reference (if using custom registry)

Edit `kubernetes/opentelemetry-demo.yaml` line 1372:
```yaml
# Change from:
image: ghcr.io/splunk/opentelemetry-demo/otel-fraud-detection:2.1.0

# To your new image:
image: YOUR_REGISTRY/fraud-detection:VERSION
```

### 3. Apply the Updated Deployment

```bash
cd /Users/phagen/GIT/opentelemetry-demo-Splunk

# Apply the updated manifest
kubectl apply -f kubernetes/opentelemetry-demo.yaml

# Or if you only want to update fraud-detection:
kubectl rollout restart deployment/fraud-detection -n otel-demo
```

### 4. Verify Deployment

```bash
# Check fraud-detection pod status
kubectl get pods -n otel-demo -l app.kubernetes.io/component=fraud-detection

# Watch the logs for successful database initialization
kubectl logs -f -n otel-demo -l app.kubernetes.io/component=fraud-detection

# Look for these log messages:
# - "Database initialized successfully"
# - "OrderLogs table verified/created successfully"
# - "Consumed record with orderId: ..."
# - "Order <id> logged to database"
```

### 5. Check SQL Server

```bash
# Get SQL Server pod
kubectl get pods -n sql -l app=sql-express

# Connect to SQL Server
kubectl exec -it sql-express-0 -n sql -- /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P 'ChangeMe_SuperStrong123!'

# In sqlcmd, run:
# SELECT name FROM sys.databases;
# GO
# USE FraudDetection;
# GO
# SELECT COUNT(*) FROM OrderLogs;
# GO
```

## Verification Queries

Once orders start flowing:

```sql
-- Port-forward to access SQL Server locally
-- kubectl port-forward -n sql svc/sql-express 1433:1433

-- Connect with any SQL client to localhost:1433
-- Username: sa
-- Password: ChangeMe_SuperStrong123!

-- View recent orders
USE FraudDetection;
GO

SELECT TOP 10
    order_id,
    shipping_tracking_id,
    shipping_city,
    shipping_country,
    items_count,
    consumed_at
FROM OrderLogs
ORDER BY consumed_at DESC;
GO

-- Count total orders logged
SELECT COUNT(*) as total_orders FROM OrderLogs;
GO

-- Orders by country
SELECT
    shipping_country,
    COUNT(*) as order_count
FROM OrderLogs
GROUP BY shipping_country
ORDER BY order_count DESC;
GO
```

## Cross-Namespace Communication

The fraud-detection service (in `otel-demo` namespace) connects to SQL Server (in `sql` namespace) using the fully qualified domain name:

```
sql-express.sql.svc.cluster.local
```

This works because:
- Kubernetes DNS resolves cross-namespace services
- No NetworkPolicies blocking the traffic (check if needed)
- Both pods can communicate via ClusterIP service

## Troubleshooting

### Fraud Detection Can't Connect

```bash
# Check if SQL Server is running
kubectl get pods -n sql -l app=sql-express

# Check fraud-detection init container logs
kubectl logs -n otel-demo -l app.kubernetes.io/component=fraud-detection -c wait-for-sqlserver

# Check main container logs
kubectl logs -n otel-demo -l app.kubernetes.io/component=fraud-detection

# Test connectivity from fraud-detection pod
kubectl exec -it FRAUD_POD_NAME -n otel-demo -- nc -zv sql-express.sql.svc.cluster.local 1433
```

### Database Not Created

```bash
# Manually create database
kubectl exec -it sql-express-0 -n sql -- /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P 'ChangeMe_SuperStrong123!' -Q "CREATE DATABASE FraudDetection"

# Verify
kubectl exec -it sql-express-0 -n sql -- /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P 'ChangeMe_SuperStrong123!' -Q "SELECT name FROM sys.databases"
```

### No Orders Being Logged

1. Check Kafka is producing orders:
```bash
kubectl logs -n otel-demo -l app.kubernetes.io/component=checkout
```

2. Check fraud-detection is consuming:
```bash
kubectl logs -n otel-demo -l app.kubernetes.io/component=fraud-detection | grep "Consumed record"
```

3. Check for database errors:
```bash
kubectl logs -n otel-demo -l app.kubernetes.io/component=fraud-detection | grep -i "error\|exception\|failed"
```

## Files Changed

### Modified
- `kubernetes/opentelemetry-demo.yaml` - Updated fraud-detection deployment config

### Code Files (already created)
- `src/fraud-detection/build.gradle.kts` - Added SQL Server dependencies
- `src/fraud-detection/src/main/kotlin/frauddetection/DatabaseConfig.kt` - Database connection
- `src/fraud-detection/src/main/kotlin/frauddetection/OrderLogRepository.kt` - Database operations
- `src/fraud-detection/src/main/kotlin/frauddetection/main.kt` - Integrated database logging

### Documentation
- `src/fraud-detection/SQL_SERVER_SETUP.md` - Comprehensive setup guide
- `src/fraud-detection/sql/init-database.sql` - Manual database setup script
- `src/fraud-detection/DEPLOYMENT_CHANGES.md` - This file

### Not Needed
- ~~`src/fraud-detection/kubernetes/sqlserver-deployment.yaml`~~ - Not needed, use existing SQL Server

## Next Steps

1. **Build and deploy** the updated fraud-detection service
2. **Generate some orders** through the demo application
3. **Query the database** to verify orders are being logged
4. **Add fraud detection logic** using the logged order data
5. **Create dashboards** to visualize fraud patterns

## Production Considerations

For production use, you should:

1. **Use secrets** instead of hardcoded passwords:
   ```yaml
   - name: SQL_SERVER_PASSWORD
     valueFrom:
       secretKeyRef:
         name: mssql-secrets
         key: SA_PASSWORD
   ```

2. **Enable SSL/TLS** for database connections
3. **Add resource limits** appropriate for your load
4. **Set up backups** for the SQL Server PVC
5. **Monitor database** performance and connection pool
6. **Implement retry logic** for transient database failures
7. **Add metrics** for database write success/failure rates
