# Shop Datacenter Shim Service

The Shop Datacenter Shim Service is an N-Tier Java Spring Boot application that simulates a traditional on-premises retail system deployed in a datacenter environment. This service demonstrates hybrid cloud-on-premises integration by acting as a shim that bridges local shop purchases to cloud checkout services.

## Architecture

This service follows traditional enterprise N-Tier architecture:

- **Presentation Layer**: REST controllers for shop transaction APIs
- **Business Layer**: Service classes handling local validation and cloud integration
- **Data Layer**: JPA repositories with PostgreSQL for local transaction storage
- **Integration Layer**: gRPC client for calling cloud checkout services

## Key Features

- **On-Premises Retail Simulation**: Mimics traditional datacenter-deployed point-of-sale systems
- **Cloud Integration**: Makes gRPC calls to cloud-hosted checkout service
- **Dual Instrumentation**: Supports both AppDynamics (traditional) and Splunk Observability (modern)
- **Enterprise Patterns**: Follows traditional enterprise Java patterns with database persistence
- **Async Processing**: Background processing with transaction state management
- **Load Generation**: Dedicated load generator simulating realistic shop transactions

## Environment Configuration

### Deployment Environment
- `deployment.environment.name`: `datacenter-b01`
- `service.namespace`: `datacenter`
- Network: Separate datacenter network (172.20.0.0/16) with bridge to cloud services

### Service Configuration
- **Service Port**: 8070
- **Database**: PostgreSQL (shop-dc-shim-db)
- **Cloud Integration**: gRPC to checkout service
- **Monitoring**: Dual AppDynamics + Splunk Observability

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

## Transaction Processing Flow

1. **Local Purchase Initiation**: Customer makes purchase at store terminal
2. **Local Validation**: Service performs on-premises validation (inventory, fraud detection)
3. **Database Storage**: Transaction stored locally with INITIATED status
4. **Cloud Submission**: gRPC call to cloud checkout service
5. **Cloud Processing**: Cloud checkout processes payment and fulfillment
6. **Confirmation**: Local transaction updated with cloud response
7. **Completion**: Final status stored locally for reconciliation

## Transaction States

- `INITIATED`: Local transaction started
- `VALIDATING`: Performing local validation checks
- `SUBMITTING_CLOUD`: Sending request to cloud checkout
- `CLOUD_PROCESSING`: Cloud is processing the request
- `COMPLETED`: Successfully completed end-to-end
- `FAILED`: Failed at any stage
- `RETRY_PENDING`: Queued for retry

## Database Schema

The service uses PostgreSQL with the following main tables:

```sql
-- Main transaction table
CREATE TABLE shop_transactions (
    id BIGSERIAL PRIMARY KEY,
    transaction_id VARCHAR(255) UNIQUE NOT NULL,
    local_order_id VARCHAR(255) NOT NULL,
    cloud_order_id VARCHAR(255),
    customer_email VARCHAR(255) NOT NULL,
    customer_name VARCHAR(255),
    total_amount DECIMAL(10,2),
    currency_code CHAR(3),
    status VARCHAR(20) NOT NULL DEFAULT 'INITIATED',
    store_location VARCHAR(100),
    terminal_id VARCHAR(50),
    -- ... additional fields for timestamps, addresses, etc.
);

-- Store location lookup
CREATE TABLE store_locations (
    id SERIAL PRIMARY KEY,
    store_code VARCHAR(10) UNIQUE NOT NULL,
    store_name VARCHAR(100) NOT NULL,
    address TEXT,
    city VARCHAR(50),
    state VARCHAR(50),
    country VARCHAR(50),
    timezone VARCHAR(50) DEFAULT 'America/New_York',
    is_active BOOLEAN DEFAULT true
);
```

## Monitoring & Observability

### Dual Instrumentation
The service supports both traditional and modern observability:

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

## Demo Use Case

This service demonstrates a real-world hybrid architecture scenario:

- **On-Premises Reality**: Traditional retail POS systems deployed in datacenters
- **Cloud Integration**: Modern checkout and payment processing in the cloud
- **Monitoring Bridge**: Shows how enterprises monitor hybrid architectures
- **Technology Evolution**: Traditional Java/DB architecture calling modern microservices

### Business Context
- Local shop systems handle inventory, pricing, customer data
- Cloud services provide scalable checkout, payment, and fulfillment
- Dual monitoring shows both traditional APM and modern observability
- Demonstrates enterprise modernization patterns

## Configuration

### Environment Variables

**Service Configuration:**
- `SHOP_DC_SHIM_PORT`: Service port (default: 8070)
- `DB_CONNECTION_STRING`: PostgreSQL connection
- `CHECKOUT_SERVICE_HOST`: Cloud checkout service host
- `CHECKOUT_SERVICE_PORT`: Cloud checkout service port

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
java -javaagent:appdynamics/javaagent.jar \
     -javaagent:opentelemetry-javaagent.jar \
     -Dagent.deployment.mode=dual \
     -Dotel.instrumentation.jdbc.enabled=true \
     -Dsplunk.profiler.enabled=true \
     -jar app.jar
```

## Local Development

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
  shop-dc-shim:
    networks:
      - datacenter-network  # On-prem network
      - default             # Cloud service connectivity
```

This network setup simulates the reality of datacenter-deployed services that need hybrid connectivity to cloud resources while maintaining network isolation for security and compliance.
