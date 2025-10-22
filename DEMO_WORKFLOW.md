# Demo Workflow - Build Up & Tear Down

Perfect for demos that get built up and torn down frequently!

## 🚀 Deploy (One Command)

```bash
cd /Users/phagen/GIT/opentelemetry-demo-Splunk
kubectl apply -f kubernetes/opentelemetry-demo.yaml
```

Wait ~3 minutes for everything to initialize.

## 🧹 Tear Down (One Command)

```bash
./cleanup.sh
```

This script:
- ✅ Deletes all deployments, services, statefulsets
- ✅ Cleans up all PVCs (prevents corrupted data)
- ✅ Ensures fresh start on next deploy

## What's Configured for Easy Demos

### SQL Server StatefulSet
**Added automatic PVC cleanup:**
```yaml
persistentVolumeClaimRetentionPolicy:
  whenDeleted: Delete    # Auto-delete PVC when StatefulSet deleted
  whenScaled: Delete     # Auto-delete PVC when scaled down
```

This means:
- `kubectl delete` will automatically remove the PVC
- No corrupted SQL Server data on next deploy
- Clean slate every time

### Fraud Detection Service
**Auto-initializes everything:**
- Creates `FraudDetection` database if missing
- Creates `OrderLogs` table if missing
- Logs every Kafka order message

## Complete Demo Cycle

### 1. Deploy
```bash
kubectl apply -f kubernetes/opentelemetry-demo.yaml
```

### 2. Verify
```bash
# Check pods are running
kubectl get pods -n otel-demo
kubectl get pods -n sql

# Watch fraud-detection logs
kubectl logs -f -n otel-demo -l app.kubernetes.io/component=fraud-detection
```

### 3. Use the Demo
```bash
# Access frontend
kubectl port-forward -n otel-demo svc/frontend 8080:8080
# Browse to http://localhost:8080 and place orders

# Access SQL Server
kubectl port-forward -n sql svc/sql-express 1433:1433
# Connect to localhost:1433 with sa/ChangeMe_SuperStrong123!
```

### 4. Query Data
```bash
kubectl exec -it sql-express-0 -n sql -- /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P 'ChangeMe_SuperStrong123!' -Q "SELECT COUNT(*) FROM FraudDetection.dbo.OrderLogs"
```

### 5. Tear Down
```bash
./cleanup.sh
```

## Troubleshooting

### SQL Server in CrashLoopBackOff

**Cause:** Corrupted PVC from previous deployment

**Fix:**
```bash
kubectl delete statefulset sql-express -n sql
kubectl delete pvc data-sql-express-0 -n sql
kubectl apply -f kubernetes/opentelemetry-demo.yaml
```

### Fraud Detection Stuck "waiting for sql-express"

**Cause:** SQL Server not ready

**Fix:**
```bash
# Check SQL Server status
kubectl get pods -n sql
kubectl logs sql-express-0 -n sql

# If SQL Server is crashing, clean and redeploy
./cleanup.sh
kubectl apply -f kubernetes/opentelemetry-demo.yaml
```

## Files Modified for Demo Workflow

### Changed
- `kubernetes/opentelemetry-demo.yaml`
  - Line 343-345: Added `persistentVolumeClaimRetentionPolicy` to sql-express StatefulSet
  - Line 1372: Updated fraud-detection image to `2.1.3-sql.1`
  - Line 1402-1411: Added SQL Server environment variables
  - Line 1423-1428: Added wait-for-sqlserver init container

### Added
- `cleanup.sh` - Automated cleanup script
- `src/fraud-detection/build-fraud-detection.sh` - Build script
- All fraud-detection code for SQL Server logging

## Quick Reference

| Action | Command |
|--------|---------|
| Deploy | `kubectl apply -f kubernetes/opentelemetry-demo.yaml` |
| Tear Down | `./cleanup.sh` |
| Watch Logs | `kubectl logs -f -n otel-demo -l app.kubernetes.io/component=fraud-detection` |
| SQL Status | `kubectl get pods -n sql` |
| Access Frontend | `kubectl port-forward -n otel-demo svc/frontend 8080:8080` |
| Access SQL Server | `kubectl port-forward -n sql svc/sql-express 1433:1433` |
| Query Database | See "Query Data" section above |

## Expected Timeline

- **Deploy:** 3 minutes
- **Tear Down:** 30 seconds
- **Redeploy:** 2 minutes (with cleanup)

Perfect for rapid demo cycles! 🎯
