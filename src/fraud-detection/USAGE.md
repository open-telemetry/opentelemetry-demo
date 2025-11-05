# Fraud Detection Service - Usage Guide

## Overview

The fraud detection service consumes orders from Kafka and performs real-time fraud analysis with database logging. It uses a hybrid configuration model:
- **Environment Variables**: Control fraud detection behavior
- **Feature Flags (flagd)**: Support Kafka lag experiments only

## Environment Variables

### Fraud Detection Configuration

#### `FRAUD_MUTATION_PERCENTAGE`
Controls the percentage of orders that get mutated to trigger fraud alerts for demonstration purposes.

- **Type**: Integer
- **Range**: 5-90 (automatically coerced)
- **Default**: 20
- **Purpose**: Demo/testing - artificially creates fraudulent orders

**Example**:
```yaml
- name: FRAUD_MUTATION_PERCENTAGE
  value: "50"  # 50% of orders will be mutated to trigger fraud
```

#### `BAD_QUERY_PERCENTAGE`
Controls the percentage chance of executing intentionally inefficient database queries for monitoring demos.

- **Type**: Integer
- **Range**: 0-100
- **Default**: 0 (disabled)
- **Purpose**: Demonstrates database monitoring, slow queries, N+1 problems

**Example**:
```yaml
- name: BAD_QUERY_PERCENTAGE
  value: "10"  # 10% chance to execute a bad query pattern
```

### Database Configuration

#### `SQL_SERVER_HOST`
- **Required**: Yes
- **Example**: `sql-server-fraud.sql.svc.cluster.local`

#### `SQL_SERVER_PORT`
- **Default**: 1433
- **Example**: `"1433"`

#### `SQL_SERVER_DATABASE`
- **Required**: Yes
- **Example**: `FraudDetection`

#### `SQL_SERVER_USER`
- **Required**: Yes
- **Example**: `sa`

#### `SQL_SERVER_PASSWORD`
- **Required**: Yes
- **Example**: `"ChangeMe_SuperStrong123!"`

### Cleanup Configuration

#### `CLEANUP_RETENTION_DAYS`
- **Default**: 7
- **Purpose**: Delete order logs older than N days

#### `CLEANUP_INTERVAL_HOURS`
- **Default**: 24
- **Purpose**: How often to run cleanup

### Kafka Configuration

#### `KAFKA_ADDR`
- **Required**: Yes
- **Example**: `kafka:9092`

## Feature Flags (flagd)

### `kafkaQueueProblems`

**Purpose**: Simulates Kafka consumer lag for observability demos.

**How It Works**:
- When enabled (value > 0), the service adds a 1-second delay when processing each Kafka message
- Works in conjunction with the checkout service which floods Kafka with messages
- Creates a lag spike scenario for monitoring/alerting demos

**Type**: Integer (0 = off, >0 = on)

**Configuration**: Set via flagd configuration file (`src/flagd/demo.flagd.json`)

**Example flagd config**:
```json
{
  "kafkaQueueProblems": {
    "description": "Overloads Kafka queue while simultaneously introducing a consumer side delay leading to a lag spike",
    "state": "ENABLED",
    "variants": {
      "on": 100,
      "off": 0
    },
    "defaultVariant": "off"
  }
}
```

**Environment Variables Required**:
```yaml
- name: FLAGD_HOST
  value: flagd
- name: FLAGD_PORT
  value: "8013"
```

## Fraud Detection Behavior

### Always-On Detection
Fraud detection runs on **every order** (100% of orders are analyzed).

### Enhanced Database Queries
Each order triggers up to **6 additional database queries**:
1. **Country Risk Score** - Historical fraud rate by country (30-day window)
2. **City Risk Score** - City-specific fraud patterns (30-day window)
3. **Address History** - Check if address was previously flagged (90-day window)
4. **Order Velocity** - Detect rapid succession of similar orders (1-hour window)
5. **Shipping Cost Anomaly** - Statistical analysis using Z-score (30-day baseline)
6. **Item Count Anomaly** - Compare against regional averages (30-day baseline)

### Mutation for Demos
Based on `FRAUD_MUTATION_PERCENTAGE`, orders are randomly mutated to trigger fraud:
- High shipping costs ($50-$500)
- Large item quantities (11-30 items)
- PO Box addresses
- Suspicious cities

## Example Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fraud-detection
  labels:
    app.kubernetes.io/name: fraud-detection
    app.kubernetes.io/component: fraud-detection
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: fraud-detection
  template:
    metadata:
      labels:
        app.kubernetes.io/name: fraud-detection
    spec:
      containers:
        - name: fraud-detection
          image: ghcr.io/splunk/opentelemetry-demo/otel-fraud-detection:2.1.3-for-jeremy
          imagePullPolicy: IfNotPresent

          env:
            # ===== OpenTelemetry Configuration =====
            - name: OTEL_SERVICE_NAME
              value: fraud-detection
            - name: OTEL_EXPORTER_OTLP_ENDPOINT
              value: http://otel-collector:4318
            - name: OTEL_RESOURCE_ATTRIBUTES
              value: service.name=fraud-detection,service.namespace=opentelemetry-demo

            # ===== Kafka Configuration =====
            - name: KAFKA_ADDR
              value: kafka:9092
            - name: OTEL_INSTRUMENTATION_KAFKA_EXPERIMENTAL_SPAN_ATTRIBUTES
              value: "true"
            - name: OTEL_INSTRUMENTATION_MESSAGING_EXPERIMENTAL_RECEIVE_TELEMETRY_ENABLED
              value: "true"

            # ===== SQL Server Database Configuration =====
            - name: SQL_SERVER_HOST
              value: sql-server-fraud.sql.svc.cluster.local
            - name: SQL_SERVER_PORT
              value: "1433"
            - name: SQL_SERVER_DATABASE
              value: FraudDetection
            - name: SQL_SERVER_USER
              value: sa
            - name: SQL_SERVER_PASSWORD
              value: "ChangeMe_SuperStrong123!"  # Use secrets in production!

            # ===== Fraud Detection Configuration =====
            # Control what percentage of orders get mutated to trigger fraud alerts
            # Range: 5-90, Default: 20
            # Higher = more fraud alerts for demo purposes
            - name: FRAUD_MUTATION_PERCENTAGE
              value: "30"  # 30% of orders will trigger fraud detection

            # ===== Database Monitoring Demo Configuration =====
            # Control percentage chance of executing bad query patterns
            # Range: 0-100, Default: 0 (disabled)
            # Set to 10-20 for database monitoring demos
            - name: BAD_QUERY_PERCENTAGE
              value: "0"  # Disabled - set to 10 to enable bad query demos

            # ===== Database Cleanup Configuration =====
            # How many days to retain order logs before cleanup
            - name: CLEANUP_RETENTION_DAYS
              value: "7"  # Delete logs older than 7 days
            # How often to run cleanup (in hours)
            - name: CLEANUP_INTERVAL_HOURS
              value: "24"  # Run cleanup daily

            # ===== Feature Flag Service (for Kafka experiments) =====
            # Required for kafkaQueueProblems experiment only
            # Can be removed if not using Kafka lag demos
            - name: FLAGD_HOST
              value: flagd
            - name: FLAGD_PORT
              value: "8013"

          resources:
            limits:
              memory: 512Mi  # Increased for database connection pooling
            requests:
              memory: 256Mi
              cpu: 100m

          # Health checks
          livenessProbe:
            tcpSocket:
              port: 8080
            initialDelaySeconds: 30
            periodSeconds: 10

          readinessProbe:
            tcpSocket:
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 5

      # ===== Init Containers =====
      # Wait for dependencies to be ready before starting
      initContainers:
        # Wait for Kafka to be available
        - name: wait-for-kafka
          image: busybox:1.36
          command:
            - sh
            - -c
            - |
              until nc -z kafka 9092; do
                echo "Waiting for Kafka..."
                sleep 2
              done
              echo "Kafka is ready!"

        # Wait for SQL Server to be available
        - name: wait-for-sql
          image: busybox:1.36
          command:
            - sh
            - -c
            - |
              until nc -z sql-server-fraud.sql.svc.cluster.local 1433; do
                echo "Waiting for SQL Server..."
                sleep 2
              done
              echo "SQL Server is ready!"

        # Optional: Wait for flagd (only needed for Kafka experiments)
        - name: wait-for-flagd
          image: busybox:1.36
          command:
            - sh
            - -c
            - |
              until nc -z flagd 8013; do
                echo "Waiting for flagd..."
                sleep 2
              done
              echo "flagd is ready!"
```

## Configuration Examples

### High Demo Load (Lots of Fraud Alerts)
```yaml
- name: FRAUD_MUTATION_PERCENTAGE
  value: "80"  # 80% of orders trigger fraud
- name: BAD_QUERY_PERCENTAGE
  value: "20"  # 20% chance of bad queries
```

### Production-Like (Low Fraud Rate)
```yaml
- name: FRAUD_MUTATION_PERCENTAGE
  value: "5"   # Only 5% of orders trigger fraud
- name: BAD_QUERY_PERCENTAGE
  value: "0"   # No bad queries
```

### Database Monitoring Demo
```yaml
- name: FRAUD_MUTATION_PERCENTAGE
  value: "10"  # Low fraud rate
- name: BAD_QUERY_PERCENTAGE
  value: "30"  # 30% chance of bad queries - creates monitoring scenarios
```

### Kafka Lag Experiment
Enable via flagd UI or configuration:
```json
{
  "kafkaQueueProblems": {
    "defaultVariant": "on"  // Enable the experiment
  }
}
```

Then monitor:
- Kafka consumer lag metrics
- Service latency increase
- Queue depth growth

## Monitoring

### Key Metrics to Watch

**Fraud Detection**:
- Fraud alert count and severity distribution
- Risk score averages
- Country/city fraud patterns

**Database Performance**:
- Query execution times (watch for the 6 fraud check queries)
- Connection pool utilization
- Bad query execution frequency (if enabled)

**Kafka**:
- Consumer lag (especially with `kafkaQueueProblems` flag)
- Message processing rate
- Error rates

### Log Messages

**Fraud Alerts**:
```
🚨 FRAUD ALERT #123: orderId=abc-123, severity=HIGH, score=0.85, reason=Very high shipping cost: $250
```

**Bad Query Execution** (when enabled):
```
⚠️ BAD QUERY: Full table scan on OrderLogs, total=50000
⚠️ BAD QUERY: N+1 problem, executed 11 queries instead of 1 JOIN
```

**Kafka Experiment**:
```
FeatureFlag 'kafkaQueueProblems' is enabled, sleeping 1 second
```

## Best Practices

1. **Start with defaults** - 20% fraud mutation is good for most demos
2. **Gradually increase** - If you need more fraud alerts, increase `FRAUD_MUTATION_PERCENTAGE` incrementally
3. **Use bad queries sparingly** - Set `BAD_QUERY_PERCENTAGE` to 10-20% max to avoid overwhelming the database
4. **Monitor database load** - The 6 additional fraud checks create significant database activity
5. **Use secrets** - Always use Kubernetes secrets for `SQL_SERVER_PASSWORD` in production
6. **Adjust retention** - Set `CLEANUP_RETENTION_DAYS` based on your demo/testing duration needs
7. **Resource limits** - Increase memory limits if you see OOM errors with high mutation rates

## Troubleshooting

### No Fraud Alerts Appearing
- Check `FRAUD_MUTATION_PERCENTAGE` is set (default is 20%)
- Verify orders are flowing through Kafka
- Check database connectivity

### Too Many Fraud Alerts
- Reduce `FRAUD_MUTATION_PERCENTAGE` to 5-10%

### Database Connection Errors
- Verify `SQL_SERVER_HOST`, `SQL_SERVER_PORT`, and credentials
- Check init container logs for SQL Server readiness

### Kafka Consumer Lag
- Check if `kafkaQueueProblems` flag is accidentally enabled
- Verify Kafka broker health
- Check service resource limits

### STRING_AGG Error (8000 byte limit)
- This has been fixed in version 2.1.3-for-jeremy
- Query now limits to TOP 100 historical fraud records
