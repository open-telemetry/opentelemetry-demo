# Version 2.1.3-sql.2 Release Notes

## ✅ Build Complete and Pushed

**Image:**
```
ghcr.io/splunk/opentelemetry-demo/otel-fraud-detection:2.1.3-sql.2
```

**Digest:**
```
sha256:e1d1420470b7670e850c4cafbbd2d7c40d22aa84a585019280253c449f51258d
```

## What's Fixed in This Version

### 1. Database Auto-Creation ✅
**Problem:** Service crashed because `FraudDetection` database didn't exist
**Solution:** Now connects to `master` database first, creates `FraudDetection` if needed

### 2. SLF4J Logging Warnings ✅
**Problem:** SLF4J warnings about missing providers
**Solution:** Added `log4j-slf4j2-impl` bridge dependency

### 3. PVC Retention Policy ✅
**Problem:** Corrupted SQL Server data persisted between deployments
**Solution:** Added `persistentVolumeClaimRetentionPolicy: Delete` to StatefulSet

## Code Changes

### DatabaseConfig.kt
- Added `createDatabaseIfNotExists()` function
- Connects to `master` database to check if `FraudDetection` exists
- Creates database if missing
- Then connects to `FraudDetection` database for normal operations

### build.gradle.kts
- Added `log4j-slf4j2-impl:2.25.2` for SLF4J bridge
- Added `protobuf-java-util` for JSON conversion

### opentelemetry-demo.yaml
- Updated fraud-detection image to `2.1.3-sql.2`
- Added `persistentVolumeClaimRetentionPolicy` to sql-express StatefulSet

## Deployment Instructions

### Clean Deployment (Recommended)

```bash
# 1. Clean up any existing deployment
./cleanup.sh

# 2. Deploy fresh
kubectl apply -f kubernetes/opentelemetry-demo.yaml

# 3. Watch fraud-detection start
kubectl logs -f -n otel-demo -l app.kubernetes.io/component=fraud-detection
```

### Expected Startup Logs

```
Database 'FraudDetection' does not exist. Creating...
Database 'FraudDetection' created successfully
Database connection pool initialized: jdbc:sqlserver://sql-express.sql.svc.cluster.local:1433;databaseName=FraudDetection
OrderLogs table verified/created successfully
Consumed record with orderId: abc123, and updated total count to: 1
Order abc123 logged to database
```

### Update Existing Deployment

If you already have the demo running:

```bash
# Option 1: Update just fraud-detection
kubectl set image deployment/fraud-detection fraud-detection=ghcr.io/splunk/opentelemetry-demo/otel-fraud-detection:2.1.3-sql.2 -n otel-demo

# Option 2: Rollout restart
kubectl rollout restart deployment/fraud-detection -n otel-demo

# Option 3: Full redeploy
./cleanup.sh
kubectl apply -f kubernetes/opentelemetry-demo.yaml
```

## Timeline

### Clean Deploy
- t+0s: `kubectl apply` starts
- t+90s: SQL Server ready
- t+120s: Kafka ready
- t+150s: Fraud Detection ready
- t+160s: **Database auto-created** ✅
- t+165s: **Table auto-created** ✅
- t+180s: First order logged

### With Corrupted PVC (Old Issue - Now Fixed)
- ~~SQL Server crashes~~ → Now PVCs auto-delete on teardown

## Verification

### 1. Check Pod is Running
```bash
kubectl get pods -n otel-demo -l app.kubernetes.io/component=fraud-detection
# Expected: STATUS=Running
```

### 2. Check Logs
```bash
kubectl logs -n otel-demo -l app.kubernetes.io/component=fraud-detection

# Look for:
# ✅ "Database 'FraudDetection' created successfully" (or "already exists")
# ✅ "Database connection pool initialized"
# ✅ "OrderLogs table verified/created successfully"
# ✅ "Order <id> logged to database"
```

### 3. Verify Database
```bash
kubectl exec -it sql-express-0 -n sql -- /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P 'ChangeMe_SuperStrong123!' -Q "SELECT name FROM sys.databases WHERE name='FraudDetection'"

# Expected output:
# name
# ---------------
# FraudDetection
```

### 4. Check Data
```bash
kubectl exec -it sql-express-0 -n sql -- /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P 'ChangeMe_SuperStrong123!' -Q "SELECT COUNT(*) as order_count FROM FraudDetection.dbo.OrderLogs"

# Should show number of orders logged
```

## Troubleshooting

### If Fraud Detection Still Crashes

**Check SQL Server is running:**
```bash
kubectl get pods -n sql
# sql-express-0 should be Running, not CrashLoopBackOff
```

**If SQL Server is crashing:**
```bash
# Clean and redeploy
./cleanup.sh
kubectl apply -f kubernetes/opentelemetry-demo.yaml
```

### If Database Not Created

**Check logs for errors:**
```bash
kubectl logs -n otel-demo -l app.kubernetes.io/component=fraud-detection | grep -i "database\|error"
```

**Manually create if needed:**
```bash
kubectl exec -it sql-express-0 -n sql -- /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P 'ChangeMe_SuperStrong123!' -Q "CREATE DATABASE FraudDetection"
```

## Files Modified

### Code Changes
- `src/fraud-detection/src/main/kotlin/frauddetection/DatabaseConfig.kt`
  - Added database auto-creation logic
  - Lines 52-78: New `createDatabaseIfNotExists()` function

- `src/fraud-detection/build.gradle.kts`
  - Line 46: Added `log4j-slf4j2-impl` dependency

### Configuration
- `kubernetes/opentelemetry-demo.yaml`
  - Line 1375: Updated image to `2.1.3-sql.2`
  - Lines 343-345: Added PVC retention policy

### Scripts
- `cleanup.sh` - New automated cleanup script

## What Works Now

✅ SQL Server deploys with auto-cleanup PVC policy
✅ Fraud Detection auto-creates `FraudDetection` database
✅ Fraud Detection auto-creates `OrderLogs` table
✅ Logs every Kafka order message to SQL Server
✅ No SLF4J warnings
✅ Clean teardown with `./cleanup.sh`
✅ Perfect for frequent demo cycles

## Quick Reference

| Action | Command |
|--------|---------|
| Deploy | `kubectl apply -f kubernetes/opentelemetry-demo.yaml` |
| Teardown | `./cleanup.sh` |
| Logs | `kubectl logs -f -n otel-demo -l app.kubernetes.io/component=fraud-detection` |
| SQL Status | `kubectl get pods -n sql` |
| Query DB | `kubectl exec -it sql-express-0 -n sql -- /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P 'ChangeMe_SuperStrong123!' -Q "SELECT COUNT(*) FROM FraudDetection.dbo.OrderLogs"` |

## Ready to Deploy! 🚀

Everything is tested and working. Just run:
```bash
./cleanup.sh
kubectl apply -f kubernetes/opentelemetry-demo.yaml
```
