# Fraud Detection Service

This service receives new orders by a Kafka topic and returns cases which are
suspected of fraud.

## Dependencies

This service requires:
- **Kafka**: For receiving order events
- **SQL Server**: For storing fraud detection data in the `FraudDetection` database

## Kubernetes Deployment

### SQL Server Database Initialization

The fraud detection service requires a SQL Server database named `FraudDetection`. The Kubernetes deployment includes automatic database initialization:

1. **ConfigMap** (`mssql-init-script`): Contains SQL script to create the database
2. **StatefulSet** (`sql-server-fraud`): SQL Server with lifecycle hook that executes the init script
3. **InitContainers**: The fraud detection deployment waits for both Kafka and SQL Server to be ready before starting

The database is automatically created when the SQL Server pod starts using a `postStart` lifecycle hook that:
- Waits 30 seconds for SQL Server to be fully initialized
- Executes the database creation script via `sqlcmd`

### Connection Details

The service connects to SQL Server using these environment variables:
- `SQL_SERVER_HOST`: `sql-server-fraud.sql.svc.cluster.local`
- `SQL_SERVER_PORT`: `1433`
- `SQL_SERVER_DATABASE`: `FraudDetection`
- `SQL_SERVER_USER`: `sa`
- `SQL_SERVER_PASSWORD`: From `mssql-secrets` secret

## Local Build

To build the protos and the service binary, run from the repo root:

```sh
cp -r ../../pb/ src/main/proto/
./gradlew shadowJar
```

## Docker Build

To build using Docker run from the repo root:

```sh
docker build -f ./src/fraud-detection/Dockerfile .
```
