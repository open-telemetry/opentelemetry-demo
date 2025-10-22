# Quick Start - Fraud Detection with SQL Server

## TL;DR - Deploy Everything

```bash
cd /Users/phagen/GIT/opentelemetry-demo-Splunk

# Deploy (one command, everything included)
kubectl apply -f kubernetes/opentelemetry-demo.yaml

# Watch it start
kubectl get pods -n otel-demo -w
kubectl get pods -n sql -w
```

Wait ~3 minutes, then:

```bash
# View fraud detection logs
kubectl logs -f -n otel-demo -l app.kubernetes.io/component=fraud-detection

# Access SQL Server
kubectl port-forward -n sql svc/sql-express 1433:1433
# Connect to localhost:1433 with sa/ChangeMe_SuperStrong123!

# Generate orders (access frontend)
kubectl port-forward -n otel-demo svc/frontend 8080:8080
# Browse to http://localhost:8080 and place orders
```

## What You Get

✅ **SQL Server Express** in `sql` namespace
- Auto-initializes with password `ChangeMe_SuperStrong123!`
- 5Gi persistent storage
- Ready in ~90 seconds

✅ **Fraud Detection Service** in `otel-demo` namespace
- Image: `ghcr.io/splunk/opentelemetry-demo/otel-fraud-detection:2.1.3-sql.1`
- **Auto-creates** `FraudDetection` database
- **Auto-creates** `OrderLogs` table with indexes
- Logs every Kafka order message to SQL Server
- Ready in ~150 seconds

✅ **Complete OpenTelemetry Demo**
- Frontend, Kafka, Checkout, all services
- Orders flow: Frontend → Checkout → Kafka → Fraud Detection → SQL Server

## Verify It's Working

```bash
# Should see: "Database initialized successfully"
kubectl logs -n otel-demo -l app.kubernetes.io/component=fraud-detection | grep "Database initialized"

# Should see orders being logged
kubectl logs -n otel-demo -l app.kubernetes.io/component=fraud-detection | grep "logged to database"

# Query the database
kubectl exec -it sql-express-0 -n sql -- /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P 'ChangeMe_SuperStrong123!' -Q "SELECT COUNT(*) FROM FraudDetection.dbo.OrderLogs"
```

## Tear Down

```bash
# Option 1: Use the cleanup script (RECOMMENDED)
./cleanup.sh

# Option 2: Manual cleanup
kubectl delete -f kubernetes/opentelemetry-demo.yaml
kubectl delete pvc --all -n sql
kubectl delete pvc --all -n otel-demo
```

**Note:** The SQL Server StatefulSet now has `persistentVolumeClaimRetentionPolicy: Delete` configured, so PVCs should auto-delete when you delete the StatefulSet. The cleanup script ensures this happens even if there are issues.

## Files You Need

Everything is in one file:
```
kubernetes/opentelemetry-demo.yaml
```

That's it!

## Image Already Built and Pushed

```
ghcr.io/splunk/opentelemetry-demo/otel-fraud-detection:2.1.3-sql.1
```

No build required unless you modify the code.

## Query Examples

```sql
-- Connect to SQL Server first
kubectl exec -it sql-express-0 -n sql -- /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P 'ChangeMe_SuperStrong123!'

-- View recent orders
USE FraudDetection;
GO

SELECT TOP 10
    order_id,
    shipping_city,
    shipping_country,
    items_count,
    consumed_at
FROM OrderLogs
ORDER BY consumed_at DESC;
GO

-- Count orders by country
SELECT shipping_country, COUNT(*) as count
FROM OrderLogs
GROUP BY shipping_country
ORDER BY count DESC;
GO
```

## Timeline

- **t+0s**: `kubectl apply` starts
- **t+90s**: SQL Server ready
- **t+120s**: Kafka ready
- **t+150s**: Fraud Detection ready, database auto-created
- **t+180s**: First orders logged to database

## Need Help?

See detailed guides:
- `SINGLE_COMMAND_DEPLOY.md` - Complete deployment guide
- `DEPLOYMENT_CHANGES.md` - What was changed
- `SQL_SERVER_SETUP.md` - SQL Server details
- `READY_TO_DEPLOY.md` - Build and verification steps

## That's All!

One file. One command. Everything works. Perfect for demos! 🚀
