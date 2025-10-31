# Shop Datacenter Shim Service

The Shop Datacenter Shim Service is an N-Tier Java Spring Boot application that simulates a traditional on-premises retail system deployed in a datacenter environment. This service demonstrates hybrid cloud-on-premises integration by acting as a shim that bridges local shop purchases to cloud checkout services.  

**NOTE:** This demo is an addition to an existing Astronomy Shop Demo and expects a deployment of such in the same k8s cluster

## Demo Use Case

This service demonstrates a real-world hybrid architecture scenario:

- **On-Premises Reality**: Traditional retail POS systems deployed in datacenters
- **Cloud Integration**: Modern checkout and payment processing in the cloud
- **Monitoring Bridge**: Shows how enterprises monitor hybrid architectures
- **Technology Evolution**: Traditional Java/DB architecture calling modern microservices

## Demo Features & Intentional Errors

### Intentional Jackson Serialization Errors
The service includes **intentional Jackson serialization errors** on the transaction status endpoint (`GET /api/shop/transaction/{transactionId}`) to demonstrate real-world error scenarios:

**What Works As Intended:**
- ✅ Purchase submissions (`POST /api/shop/purchase`) - returns 202 successfully
- ✅ Background transaction processing and database persistence
- ✅ gRPC calls to cloud checkout service 

### Business Context
- Local shop systems handle inventory, pricing, customer data
- Cloud services provide scalable checkout, payment, and fulfillment
- Dual monitoring shows both AppDynamics and Splunk Observability
- Demonstrates enterprise modernization patterns

## Environment Configuration

### Deployment Environment
**NOTE:** These new services will be in a separate environment from your Astronomy Shop Demo. Filter to both environments to see the entire service map.
- `deployment.environment.name`: `datacenter-b01`
- `service.namespace`: `datacenter`
- Network: Separate datacenter network (172.20.0.0/16) with bridge to cloud services

### Service Configuration
- **Service Port**: 8070
- **Database**: SQL Server (shop-dc-shim-db)
- **Cloud Integration**: gRPC to checkout service
- **Monitoring**: Dual AppDynamics + Splunk Observability

## Development / Contribution

### Using Demo In A Box instance (from Splunk Show Observability4Ninjas / Portfolio Demo)
**Note:** This requires the instance to have a k3s/k3d deployment with Astronomy Shop Demo
- Update and use `build-image-quay-dev.sh` to build a new image with your local changes
- Reference that new image in `k8s-addition.yaml` and copy to your instance
- `kubectl apply -f k8s-addition.yaml` will add the `shop-dc-shim-db`, `shop-dc-shim`, and `shop-dc-load-generator` pods to your cluster
- Once `shop-dc-shim` finishes spinning up (5-7min) the load generator will start sending traffic
- **For DBMon** upgrade splunk-otel-collector helm chart with `dbmon-values.yaml`
  - E.G. `helm upgrade splunk-otel-collector-1760534477 --values /home/splunk/dbmon-values.yaml splunk-otel-collector-chart/splunk-otel-collector --reuse-values`
- To delete `kubectl delete -f k8s-addition.yaml` will remove all shop-dc related resources

### Bare Metal (thar may be dragons)
**NOTE:** REQUIRES A DEPLOYMENT OF ASTRONOMY SHOP DEMO IN A LOCAL K3S CLUSTER
```bash
# Build the service
./gradlew build

# Run with local profile
java -jar build/libs/shop-dc-shim-*.jar

# Run load generator
cd load-generator
pip install -r requirements.txt
python shop_load_generator.py --url http://localhost:8070

# Docker build
docker build -t shop-dc-shim:latest .
```

## Architecture

This service follows traditional enterprise N-Tier architecture:

- **Presentation Layer**: REST controllers for shop transaction APIs
- **Business Layer**: Service classes handling local validation and cloud integration
- **Data Layer**: JPA repositories with SQL Server for local transaction storage
- **Integration Layer**: gRPC client for calling cloud checkout services

## Configuration

### Environment Variables

**Service Configuration:**
- `SHOP_DC_SHIM_PORT`: Service port (default: 8070)
- `DB_CONNECTION_STRING`: SQL Server connection string (jdbc:sqlserver://...)
- `DB_USERNAME`: Database username (default: sa)
- `DB_PASSWORD`: Database password (default: ShopPass123!)
- `CHECKOUT_SERVICE_ADDR`: Cloud checkout service address (default: checkout:8080)
- `CHECKOUT_SERVICE_HOST`: Cloud checkout service host (default: checkout)
- `CHECKOUT_SERVICE_PORT`: Cloud checkout service port (default: 8080)

**AppDynamics Configuration:**
- `APPDYNAMICS_JAVAAGENT_ENABLED`: Enable AppD agent
- `APPDYNAMICS_CONTROLLER_HOST_NAME`: AppD controller
- `APPDYNAMICS_AGENT_APPLICATION_NAME`: App name in AppD
- `APPDYNAMICS_AGENT_TIER_NAME`: Tier name in AppD

**Splunk Observability:**
- `OTEL_EXPORTER_OTLP_ENDPOINT`: OTLP collector endpoint
- `OTEL_RESOURCE_ATTRIBUTES`: Resource attributes
- `SPLUNK_PROFILER_ENABLED`: Enable profiler

### Startup Script
The service uses `start-app-dual.sh` which matches enterprise Ansible deployment patterns:

```bash
# AppDynamics + Splunk dual instrumentation
export AGENT_DEPLOYMENT_MODE=dual
java -javaagent:/opt/appdynamics/javaagent.jar \
     -Dagent.deployment.mode=dual \
     -Dotel.instrumentation.jdbc.enabled=true \
     -Dsplunk.profiler.enabled=true \
     -Dsplunk.profiler.memory.enabled=true \
     -Dsplunk.snapshot.profiler.enabled=true \
     -Dsplunk.snapshot.selection.probability=0.2 \
     -Dotel.exporter.otlp.endpoint=http://splunk-otel-collector-agent:4318 \
     -Dappdynamics.sim.enabled=true \
     -jar /app/*.jar
```

## API Endpoints

### POST /api/shop/purchase
Submit a new shop purchase for processing.

**Request Body:**
```json
{
  "customerName": "John Doe",
  "customerEmail": "john.doe@example.com",
  "totalAmount": 299.99,
  "currencyCode": "USD",
  "storeLocation": "DC-NYC-01",
  "terminalId": "TERM-001",
  "shippingAddress": {
    "streetAddress": "123 Main St",
    "city": "New York",
    "state": "NY",
    "country": "USA",
    "zipCode": "10001"
  },
  "creditCard": {
    "creditCardNumber": "4111-1111-1111-1111",
    "creditCardCvv": 123,
    "expirationMonth": 12,
    "expirationYear": 2025
  },
  "items": [
    {
      "productId": "SKU-TELE-001",
      "quantity": 1,
      "unitPrice": 299.99,
      "productName": "Professional Telescope"
    }
  ]
}
```

**Response:**
```json
{
  "transactionId": "uuid-string",
  "status": "accepted",
  "message": "Purchase request received and is being processed",
  "storeLocation": "DC-NYC-01",
  "terminalId": "TERM-001"
}
```

### GET /api/shop/transaction/{transactionId}
Check the status of a shop transaction.

**Response:**
```json
{
  "transactionId": "uuid-string",
  "localOrderId": "DC-NYC-TERM001-123456",
  "cloudOrderId": "cloud-order-uuid",
  "status": "COMPLETED",
  "customerEmail": "john.doe@example.com",
  "customerName": "John Doe",
  "totalAmount": 299.99,
  "currencyCode": "USD",
  "storeLocation": "DC-NYC-01",
  "terminalId": "TERM-001",
  "createdAt": "2024-01-01T10:00:00",
  "processedAt": "2024-01-01T10:00:30",
  "cloudSubmittedAt": "2024-01-01T10:00:15",
  "cloudConfirmedAt": "2024-01-01T10:00:30",
  "errorMessage": ""
}
```

### GET /api/shop/store/{storeLocation}/transactions
Get recent transactions for a specific store location.

**Query Parameters:**
- `hours` (optional): Number of hours to look back (default: 24)

**Response:**
```json
{
  "storeLocation": "DC-NYC-01",
  "hoursBack": 24,
  "transactionCount": 15,
  "transactions": [
    {
      "transactionId": "uuid-string",
      "status": "COMPLETED",
      "totalAmount": 299.99,
      "createdAt": "2024-01-01T10:00:00"
    }
  ]
}
```

### GET /api/shop/health
Health check endpoint with transaction statistics.

**Response:**
```json
{
  "status": "healthy",
  "service": "shop-dc-shim",
  "environment": "datacenter-b01",
  "description": "On-premises shop datacenter shim service for cloud checkout integration",
  "transactions": {
    "initiated": 150,
    "validating": 5,
    "submittingCloud": 2,
    "completed": 140,
    "failed": 3,
    "completedLastHour": 25,
    "avgProcessingTimeSeconds": 2.3
  }
}
```



## Request Flow Through Java Components

### End-to-End Transaction Processing Flow

When a purchase request is submitted to the shop-dc-shim service, it flows through these Java components:

1. **ShopController.processPurchase()** (`/api/shop/purchase`)
   - Receives HTTP POST request with purchase details
   - Creates OpenTelemetry span for tracing
   - Validates request using `@Valid` annotation
   - Calls `ShopTransactionService.initiateShopPurchase()`
   - Returns HTTP 202 (Accepted) with transaction ID

2. **ShopTransactionService.initiateShopPurchase()**
   - Generates unique transaction ID and local order ID
   - Creates `ShopTransaction` entity with INITIATED status
   - Serializes shipping address and items to JSON
   - Saves transaction to SQL Server database
   - Calls `processTransactionAsync()` for background processing
   - Returns transaction ID to controller

3. **ShopTransactionService.processTransactionAsync()** (Async)
   - Runs in background thread pool
   - Updates transaction status to VALIDATING
   - Calls `performLocalValidation()` for on-premises validation
   - Updates status to SUBMITTING_CLOUD
   - Calls `CloudCheckoutService.submitToCloudCheckout()`
   - Processes cloud response and updates transaction status
   - Saves final transaction state to database

4. **ShopTransactionService.performLocalValidation()**
   - Simulates on-premises validation logic:
     - Local inventory checks
     - Customer information validation
     - Fraud detection
     - Payment limits verification
   - Adds processing delay to simulate real validation

5. **CloudCheckoutService.submitToCloudCheckout()**
   - Creates gRPC channel to checkout service
   - Generates unique user ID for cloud transaction
   - Calls `buildGrpcRequest()` to create protobuf request
   - Makes blocking gRPC call to checkout service
   - Returns `CloudCheckoutResult` with success/failure status

6. **CloudCheckoutService.buildGrpcRequest()**
   - Converts shop purchase request to protobuf format
   - Builds `Address`, `CreditCardInfo`, and `PlaceOrderRequest` messages
   - Returns properly formatted gRPC request

The entire flow is instrumented with OpenTelemetry spans for distributed tracing, and each step updates the transaction status in the SQL Server database for monitoring and reconciliation.

## Transaction Processing Flow

1. **Local Purchase Initiation**: Customer makes purchase at store terminal
2. **Local Validation**: Service performs on-premises validation (inventory, fraud detection)
3. **Database Storage**: Transaction stored locally with INITIATED status
4. **Cloud Submission**: gRPC call to cloud checkout service
5. **Cloud Processing**: Cloud checkout processes payment and fulfillment
6. **Confirmation**: Local transaction updated with cloud response
7. **Completion**: Final status stored locally for reconciliation





## Monitoring & Observability


**AppDynamics (Traditional APM)**
- Application: `shop-dc-shim-service`
- Tier: `shop-dc-shim`  
- Node: Datacenter node naming
- Deep application monitoring for traditional enterprise environments

**Splunk Observability (OpenTelemetry)**
- Service: `shop-dc-shim`
- Environment: `datacenter-b01`
- Namespace: `datacenter`
- Modern distributed tracing and metrics

### Key Telemetry Data

**Traces show:**
- On-premises transaction initiation
- Local validation processing
- gRPC calls to cloud checkout service
- Cross-environment communication patterns
- End-to-end transaction lifecycle

**Resource Attributes:**
- `service.name=shop-dc-shim`
- `deployment.environment.name=datacenter-b01`
- `service.namespace=datacenter`
- `service.version=2.1.3`

## Load Generation

The service includes a dedicated Python load generator that simulates realistic on-premises shop traffic:

### Store Locations
- DC-NYC-01: Manhattan Flagship (4 terminals)
- DC-NYC-02: Brooklyn Heights (3 terminals)  
- DC-BOS-01: Boston Downtown (2 terminals)
- DC-PHI-01: Philadelphia Center (3 terminals)
- DC-DC-01: Washington Capitol (2 terminals)

### Load Patterns
- **Continuous**: Steady transaction rate (configurable TPM)
- **Burst**: High-volume concurrent transactions
- **Enterprise**: Batch processing patterns

### Usage
```bash
# Continuous load (10 TPM for 1 hour)
python shop_load_generator.py --mode continuous --tpm 10 --duration 60

# Burst load (50 concurrent transactions)
python shop_load_generator.py --mode burst --concurrent 20 --total 50

# Single transaction test
python shop_load_generator.py --mode single
```





## Docker Compose Setup

The service is configured to run in a separate datacenter network while maintaining connectivity to cloud services:

```yaml
networks:
  datacenter-network:
    name: datacenter-b01
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16

services:
  shop-dc-shim-db:
    image: mcr.microsoft.com/mssql/server:2022-latest
    environment:
      - ACCEPT_EULA=Y
      - MSSQL_SA_PASSWORD=ShopPass123!
    ports:
      - "1433:1433"
    networks:
      - datacenter-network

  shop-dc-shim:
    depends_on:
      - shop-dc-shim-db
    environment:
      - DB_CONNECTION_STRING=jdbc:sqlserver://shop-dc-shim-db:1433;databaseName=master;encrypt=false;trustServerCertificate=true
      - DB_USERNAME=sa
      - DB_PASSWORD=ShopPass123!
    networks:
      - datacenter-network  # On-prem network
      - default             # Cloud service connectivity
```

This network setup simulates the reality of datacenter-deployed services that need hybrid connectivity to cloud resources while maintaining network isolation for security and compliance.
