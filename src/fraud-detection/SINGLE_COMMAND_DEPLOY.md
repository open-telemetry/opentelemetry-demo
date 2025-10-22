# Single Command Deployment Guide

## ✅ Everything is Self-Contained in One File!

All components needed for fraud detection with SQL Server logging are included in:
```
kubernetes/opentelemetry-demo.yaml
```

## What Gets Deployed

When you apply the single YAML file, you get:

### 1. SQL Server Express (lines 303-400)
- **Namespace**: `sql`
- **Secret**: `mssql-secrets` with password `ChangeMe_SuperStrong123!`
- **StatefulSet**: `sql-express` with 5Gi PVC
- **Service**: `sql-express.sql.svc.cluster.local:1433`
- **Resources**: 1Gi-2Gi memory, 250m-1 CPU
- **Probes**: Readiness and liveness checks

### 2. Fraud Detection Service (lines 1348-1429)
- **Image**: `ghcr.io/splunk/opentelemetry-demo/otel-fraud-detection:2.1.3-sql.1`
- **Environment**: SQL Server connection configured
- **Init Containers**:
  - `wait-for-kafka` - Waits for Kafka to be ready
  - `wait-for-sqlserver` - Waits for SQL Server to be ready
- **Functionality**: Consumes Kafka orders and logs to SQL Server

### 3. All Other Demo Components
- Frontend, Checkout, Payment, Cart, etc.
- Kafka, Flagd, and other services

## Single Command Deploy

```bash
cd /Users/phagen/GIT/opentelemetry-demo-Splunk

# Deploy everything
kubectl apply -f kubernetes/opentelemetry-demo.yaml

# That's it! One command does it all.
```

## What Happens (Automatic Initialization)

### Phase 1: Infrastructure (0-60 seconds)
```
1. Namespaces created (otel-demo, sql)
2. Secrets created (mssql-secrets)
3. ConfigMaps created
4. Services created
5. PVCs created (sql-express-data)
```

### Phase 2: SQL Server Startup (60-120 seconds)
```
1. SQL Server StatefulSet starts
2. SQL Server Express initializes
3. SA password configured
4. Readiness probe passes (port 1433 open)
5. Service becomes available: sql-express.sql.svc.cluster.local
```

### Phase 3: Kafka & Services (60-180 seconds)
```
1. Kafka starts up
2. Other demo services start
3. Orders topic created
```

### Phase 4: Fraud Detection Startup (120-240 seconds)
```
1. Init container waits for Kafka (port 9092)
2. Init container waits for SQL Server (port 1433)
3. Main container starts
4. Connects to SQL Server
5. AUTO-CREATES: FraudDetection database
6. AUTO-CREATES: OrderLogs table with indexes
7. Subscribes to Kafka orders topic
8. Starts consuming and logging orders
```

## Verify Deployment

### Quick Status Check
```bash
# Check all pods in otel-demo namespace
kubectl get pods -n otel-demo

# Check SQL Server in sql namespace
kubectl get pods -n sql

# Check fraud-detection specifically
kubectl get pods -n otel-demo -l app.kubernetes.io/component=fraud-detection
```

### Watch Fraud Detection Logs
```bash
kubectl logs -f -n otel-demo -l app.kubernetes.io/component=fraud-detection

# Expected output:
# Database initialized successfully
# OrderLogs table verified/created successfully
# Consumed record with orderId: abc123, and updated total count to: 1
# Order abc123 logged to database
```

### Check SQL Server Status
```bash
# Get SQL Server pod
kubectl get pods -n sql -l app=sql-express

# Expected:
# NAME              READY   STATUS    RESTARTS   AGE
# sql-express-0     1/1     Running   0          3m
```

### Verify Database Was Auto-Created
```bash
# Connect to SQL Server
kubectl exec -it sql-express-0 -n sql -- /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P 'ChangeMe_SuperStrong123!'

# Run these commands:
SELECT name FROM sys.databases;
GO
# Should show: FraudDetection

USE FraudDetection;
GO

SELECT COUNT(*) as order_count FROM OrderLogs;
GO
# Will show number of orders logged
```

## Single Command Teardown

When you're done with the demo:

```bash
# Delete everything
kubectl delete -f kubernetes/opentelemetry-demo.yaml

# Optionally clean up PVCs (will delete SQL Server data)
kubectl delete pvc -n sql --all
kubectl delete pvc -n otel-demo --all

# Optionally delete namespaces
kubectl delete namespace otel-demo
kubectl delete namespace sql
```

## Build → Deploy → Test Workflow

For rapid iteration:

```bash
# 1. Build new image
cd /Users/phagen/GIT/opentelemetry-demo-Splunk/src/fraud-detection
./build-fraud-detection.sh 2.1.3-sql.1

# 2. Deploy (or re-deploy)
cd /Users/phagen/GIT/opentelemetry-demo-Splunk
kubectl apply -f kubernetes/opentelemetry-demo.yaml

# 3. Watch logs
kubectl logs -f -n otel-demo -l app.kubernetes.io/component=fraud-detection

# 4. Generate orders (access frontend in browser)
# Then watch them appear in database

# 5. Query database
kubectl port-forward -n sql svc/sql-express 1433:1433
# Connect with SQL client to localhost:1433
```

## For Frequent Build/Teardown Cycles

### Fast Teardown (Keep PVCs)
```bash
# Delete deployments but keep data
kubectl delete deployment,statefulset --all -n otel-demo
kubectl delete statefulset --all -n sql

# This preserves:
# - PVCs (SQL Server data persists)
# - Secrets (passwords)
# - ConfigMaps
# - Services
```

### Fast Redeploy
```bash
# Reapply (much faster since PVCs exist)
kubectl apply -f kubernetes/opentelemetry-demo.yaml

# SQL Server will:
# - Reattach to existing PVC
# - FraudDetection database already exists
# - OrderLogs table already has data
# - Continue logging new orders
```

### Complete Teardown (Delete Everything)
```bash
# Nuclear option - deletes all data
kubectl delete -f kubernetes/opentelemetry-demo.yaml
kubectl delete pvc --all -n otel-demo
kubectl delete pvc --all -n sql

# Start fresh next time
```

## Timeline Expectations

### First Deployment (Cold Start)
```
kubectl apply: ~10 seconds
PVC creation: ~30 seconds
SQL Server ready: ~90 seconds
Kafka ready: ~120 seconds
Fraud-detection ready: ~150 seconds
Database auto-created: ~160 seconds
First order logged: ~180 seconds
---
Total: ~3 minutes
```

### Subsequent Deployments (With PVCs)
```
kubectl apply: ~10 seconds
SQL Server ready: ~30 seconds
Kafka ready: ~60 seconds
Fraud-detection ready: ~90 seconds
Database exists (no creation): ~95 seconds
First order logged: ~120 seconds
---
Total: ~2 minutes
```

### Teardown
```
kubectl delete: ~30 seconds
PVC cleanup: ~10 seconds (if deleting)
---
Total: ~40 seconds
```

## Troubleshooting

### Fraud Detection Won't Start

**Check init containers:**
```bash
POD=$(kubectl get pods -n otel-demo -l app.kubernetes.io/component=fraud-detection -o jsonpath='{.items[0].metadata.name}')

# Check if waiting for SQL Server
kubectl logs -n otel-demo $POD -c wait-for-sqlserver

# Check if waiting for Kafka
kubectl logs -n otel-demo $POD -c wait-for-kafka
```

**Common causes:**
- SQL Server not ready yet (wait 2-3 minutes)
- PVC provisioning slow (check PVC status)
- Insufficient cluster resources

### SQL Server Won't Start

```bash
# Check SQL Server pod
kubectl describe pod sql-express-0 -n sql

# Check PVC
kubectl get pvc -n sql

# Common issues:
# - No storage class available
# - Insufficient disk space
# - Security context issues
```

**Fix storage class:**
```bash
# List available storage classes
kubectl get sc

# If none exist, create a local-path one (for testing):
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/master/deploy/local-path-storage.yaml
```

### Database Not Created

```bash
# Check fraud-detection logs for errors
kubectl logs -n otel-demo -l app.kubernetes.io/component=fraud-detection | grep -i "database\|error\|exception"

# Manually create if needed:
kubectl exec -it sql-express-0 -n sql -- /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P 'ChangeMe_SuperStrong123!' -Q "CREATE DATABASE FraudDetection"
```

### No Orders Appearing

```bash
# 1. Check if orders are being created
kubectl logs -n otel-demo -l app.kubernetes.io/component=checkout | grep -i order

# 2. Check Kafka
kubectl logs -n otel-demo -l app=kafka

# 3. Check fraud-detection is consuming
kubectl logs -n otel-demo -l app.kubernetes.io/component=fraud-detection | grep "Consumed record"

# 4. Check database writes
kubectl logs -n otel-demo -l app.kubernetes.io/component=fraud-detection | grep "logged to database"
```

## Advanced: Update Image Without Full Redeploy

If you only changed fraud-detection code:

```bash
# Build new image (increment version)
./build-fraud-detection.sh 2.1.3-sql.2

# Update the image in YAML
# Edit kubernetes/opentelemetry-demo.yaml line 1372

# Restart just fraud-detection
kubectl rollout restart deployment/fraud-detection -n otel-demo

# Or patch the image directly (no YAML edit needed)
kubectl set image deployment/fraud-detection fraud-detection=ghcr.io/splunk/opentelemetry-demo/otel-fraud-detection:2.1.3-sql.2 -n otel-demo
```

## Port Forwarding for Local Access

### SQL Server
```bash
# Forward SQL Server port
kubectl port-forward -n sql svc/sql-express 1433:1433

# Connect with:
# Host: localhost
# Port: 1433
# User: sa
# Password: ChangeMe_SuperStrong123!
# Database: FraudDetection
```

### Frontend
```bash
# Forward frontend (to place orders)
kubectl port-forward -n otel-demo svc/frontend 8080:8080

# Access: http://localhost:8080
```

## Validation Checklist

After deployment, verify:

- [ ] `kubectl get pods -n sql` shows sql-express-0 Running
- [ ] `kubectl get pods -n otel-demo` shows fraud-detection Running
- [ ] `kubectl logs -n otel-demo -l app.kubernetes.io/component=fraud-detection` shows "Database initialized"
- [ ] SQL Server has FraudDetection database
- [ ] OrderLogs table exists with proper schema
- [ ] Orders are being logged (count increases)

## Summary

**Single file contains everything:**
✅ SQL Server Express with persistent storage
✅ Fraud Detection service with SQL logging
✅ All demo components (Frontend, Kafka, etc.)
✅ Automatic database and table creation
✅ Init containers ensure proper startup order
✅ Cross-namespace networking configured

**Single command deploys:**
```bash
kubectl apply -f kubernetes/opentelemetry-demo.yaml
```

**Single command tears down:**
```bash
kubectl delete -f kubernetes/opentelemetry-demo.yaml
```

**Perfect for demos that build up and tear down often!**
