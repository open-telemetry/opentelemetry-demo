# Contributing to Shop-DC-Shim Service

Welcome! This guide will help you understand how the shop-dc-shim service works and how to add or modify endpoints and database queries.

## Table of Contents
1. [Understanding the Request Flow](#understanding-the-request-flow)
2. [Tracing Endpoints to SQL Queries](#tracing-endpoints-to-sql-queries)
3. [How to Add a New Endpoint](#how-to-add-a-new-endpoint)
4. [How to Add or Modify Database Queries](#how-to-add-or-modify-database-queries)
5. [Testing Your Changes](#testing-your-changes)
6. [Debugging Tips](#debugging-tips)
7. [Common Patterns](#common-patterns)

---

## Understanding the Request Flow

The service follows a standard N-Tier architecture. Here's how a request flows through the system:

```
HTTP Request
    ↓
Controller (handles HTTP, validation)
    ↓
Service (business logic, async processing)
    ↓
Repository (database queries)
    ↓
Database (SQL Server)
```

### The Layers Explained

**Controller Layer** (`controller/ShopController.java`)
- Handles HTTP requests and responses
- Validates incoming data using `@Valid`
- Creates OpenTelemetry spans for tracing
- Delegates business logic to Service layer
- Returns HTTP status codes and JSON responses

**Service Layer** (`service/ShopTransactionService.java` and `service/CloudCheckoutService.java`)
- Contains business logic
- Manages transactions with `@Transactional`
- Handles async processing with `@Async`
- Calls repository methods to access database
- Makes gRPC calls to cloud services

**Repository Layer** (`repository/ShopTransactionRepository.java`)
- Defines database queries
- Extends `JpaRepository` for automatic CRUD operations
- Custom queries using `@Query` annotation
- No business logic - just data access

**Entity Layer** (`entity/ShopTransaction.java`)
- Represents database table structure
- Maps Java objects to SQL tables using JPA
- Defines column names, types, and constraints

---

## Tracing Endpoints to SQL Queries

Let's trace each endpoint to see exactly which SQL queries it executes.

### Endpoint 1: `POST /api/shop/purchase`

**Step-by-Step Trace:**

1. **Controller Entry Point**
   - File: `controller/ShopController.java`
   - Method: `processPurchase()` (line 32)
   - HTTP Method: POST
   - Path: `/api/shop/purchase`

2. **Service Call**
   - Calls: `transactionService.initiateShopPurchase(request)` (line 44)
   - File: `service/ShopTransactionService.java`
   - Method: `initiateShopPurchase()` (line 41)

3. **Database Operations**
   - Line 81: `transactionRepository.save(transaction)`
   - **SQL Generated**: 
     ```sql
     INSERT INTO shop_transactions 
     (transaction_id, local_order_id, customer_email, customer_name, 
      total_amount, currency_code, store_location, terminal_id, 
      status, shipping_address, items_json, created_at, retry_count)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'INITIATED', ?, ?, GETDATE(), 0)
     ```
   - This also triggers the **check constraint** which runs expensive subqueries (see `schema.sql` lines 89-97)

4. **Async Processing** (runs in background)
   - Line 87: `processTransactionAsync(transactionId, request)`
   - This method executes additional queries:

   **Query 1** (line 110):
   ```java
   transactionRepository.findByTransactionId(transactionId)
   ```
   - Executes the **intentionally bad query** from `ShopTransactionRepository.java` (lines 19-34)
   - This query has CROSS JOINs and multiple subqueries!

   **Query 2** (line 117):
   ```java
   transactionRepository.save(transaction)  // Update status to VALIDATING
   ```
   - SQL: `UPDATE shop_transactions SET status = 'VALIDATING' WHERE id = ?`

   **Query 3** (line 125):
   ```java
   transactionRepository.save(transaction)  // Update status to SUBMITTING_CLOUD
   ```
   - SQL: `UPDATE shop_transactions SET status = 'SUBMITTING_CLOUD', cloud_submitted_at = ? WHERE id = ?`

   **Query 4** (line 153):
   ```java
   transactionRepository.save(transaction)  // Final status update
   ```
   - SQL: `UPDATE shop_transactions SET status = ?, cloud_order_id = ?, cloud_confirmed_at = ?, processed_at = ? WHERE id = ?`

---

### Endpoint 2: `GET /api/shop/transaction/{transactionId}`

**Step-by-Step Trace:**

1. **Controller Entry Point**
   - File: `controller/ShopController.java`
   - Method: `getTransactionStatus()` (line 77)
   - HTTP Method: GET
   - Path: `/api/shop/transaction/{transactionId}`

2. **Service Call**
   - Line 85: `transactionService.getTransactionStatus(transactionId)`
   - File: `service/ShopTransactionService.java`
   - Method: `getTransactionStatus()` (line 193)

3. **Database Operations**
   - Line 195: `transactionRepository.findByTransactionId(transactionId)`
   - **SQL Executed**: The terrible query from `ShopTransactionRepository.java` lines 19-34
   - This query includes:
     - 2 CROSS JOINs (creates cartesian product)
     - 6 subqueries with full table scans
     - String manipulation functions
     - Unnecessary type casting

**Why is this query so bad?**
It's intentionally inefficient to demonstrate database performance monitoring! A simple query like this:
```sql
SELECT * FROM shop_transactions WHERE transaction_id = ?
```
Would be much faster, but wouldn't show the value of APM tools.

---

### Endpoint 3: `GET /api/shop/store/{storeLocation}/transactions`

**Step-by-Step Trace:**

1. **Controller Entry Point**
   - File: `controller/ShopController.java`
   - Method: `getStoreTransactions()` (line 132)
   - HTTP Method: GET
   - Path: `/api/shop/store/{storeLocation}/transactions`

2. **Service Call**
   - Line 144: `transactionService.getTransactionsByStore(storeLocation, since)`
   - File: `service/ShopTransactionService.java`
   - Method: `getTransactionsByStore()` (line 200)

3. **Database Operations**
   - Line 201: `transactionRepository.findByStoreLocationAndCreatedAtAfter(storeLocation, since)`
   - Repository method: `ShopTransactionRepository.java` line 50
   - **SQL Generated**:
     ```sql
     SELECT s.* FROM shop_transactions s 
     WHERE s.store_location = ? AND s.created_at >= ?
     ```
   - This query is efficient and uses the index on `store_location`

---

### Endpoint 4: `GET /api/shop/stats`

**Step-by-Step Trace:**

1. **Controller Entry Point**
   - File: `controller/ShopController.java`
   - Method: `getStats()` (line 181)
   - HTTP Method: GET
   - Path: `/api/shop/stats`

2. **Service Call**
   - Line 182: `transactionService.getTransactionStats()`
   - File: `service/ShopTransactionService.java`
   - Method: `getTransactionStats()` (line 255)

3. **Database Operations** (7 queries total!)
   - Lines 256-260: Five `countByStatus()` calls:
     ```sql
     SELECT COUNT(s) FROM shop_transactions s WHERE s.status = 'INITIATED'
     SELECT COUNT(s) FROM shop_transactions s WHERE s.status = 'VALIDATING'
     SELECT COUNT(s) FROM shop_transactions s WHERE s.status = 'SUBMITTING_CLOUD'
     SELECT COUNT(s) FROM shop_transactions s WHERE s.status = 'COMPLETED'
     SELECT COUNT(s) FROM shop_transactions s WHERE s.status = 'FAILED'
     ```
   - Line 263: `countCompletedTransactionsSince()`
     ```sql
     SELECT COUNT(s) FROM shop_transactions s 
     WHERE s.created_at >= ? AND s.status = 'COMPLETED'
     ```
   - Line 265: `getAverageProcessingTimeSeconds()`
     ```sql
     SELECT AVG(DATEDIFF(SECOND, created_at, cloud_confirmed_at)) 
     FROM shop_transactions 
     WHERE status = 'COMPLETED' AND created_at >= ?
     ```

---

## How to Add a New Endpoint

Let's walk through adding a new endpoint: `GET /api/shop/customer/{email}/transactions`

### Step 1: Add Repository Method

First, add the database query to `repository/ShopTransactionRepository.java`:

```java
// Add this method to the interface
@Query("SELECT s FROM ShopTransaction s WHERE s.customerEmail = :email ORDER BY s.createdAt DESC")
List<ShopTransaction> findByCustomerEmail(@Param("email") String email);
```

This will generate SQL:
```sql
SELECT * FROM shop_transactions WHERE customer_email = ? ORDER BY created_at DESC
```

### Step 2: Add Service Method

Add business logic to `service/ShopTransactionService.java`:

```java
@Transactional(readOnly = true)
public List<ShopTransaction> getTransactionsByCustomer(String email) {
    log.info("Fetching transactions for customer: {}", email);
    return transactionRepository.findByCustomerEmail(email);
}
```

**Note**: 
- Use `@Transactional(readOnly = true)` for read operations (optimizes connection pooling)
- Use `@Transactional` without parameters for write operations

### Step 3: Add Controller Endpoint

Add the HTTP endpoint to `controller/ShopController.java`:

```java
@GetMapping("/customer/{email}/transactions")
public ResponseEntity<Map<String, Object>> getCustomerTransactions(@PathVariable String email) {
    // Create OpenTelemetry span for tracing
    Span span = tracer.spanBuilder("shop_api_customer_transactions")
            .setAttribute("http.method", "GET")
            .setAttribute("http.route", "/api/shop/customer/{email}/transactions")
            .setAttribute("customer.email", email)
            .startSpan();

    try {
        List<ShopTransaction> transactions = transactionService.getTransactionsByCustomer(email);

        span.setAttribute("transaction.count", transactions.size());
        span.setAttribute("http.status_code", 200);

        return ResponseEntity.ok(Map.of(
                "customerEmail", email,
                "transactionCount", transactions.size(),
                "transactions", transactions
        ));

    } catch (Exception e) {
        span.recordException(e);
        span.setAttribute("http.status_code", 500);
        log.error("Error retrieving customer transactions for {}", email, e);

        return ResponseEntity.internalServerError()
                .body(Map.of(
                        "error", "Internal server error",
                        "message", e.getMessage()
                ));
    } finally {
        span.end();  // Always close the span!
    }
}
```

### Step 4: Test Your Endpoint

```bash
# Rebuild the application
./gradlew clean build

# Run locally
java -jar build/libs/shop-dc-shim-*.jar

# Test with curl
curl -X GET http://localhost:8070/api/shop/customer/john.doe@example.com/transactions
```

---

## How to Add or Modify Database Queries

### Method 1: Spring Data JPA Method Names (Automatic Query Generation)

Spring Data JPA can automatically generate queries from method names!

**Examples:**

```java
// Find by single field
Optional<ShopTransaction> findByLocalOrderId(String localOrderId);
// Generated SQL: SELECT * FROM shop_transactions WHERE local_order_id = ?

// Find by multiple fields
List<ShopTransaction> findByStoreLocationAndStatus(String storeLocation, TransactionStatus status);
// Generated SQL: SELECT * FROM shop_transactions WHERE store_location = ? AND status = ?

// Find with ordering
List<ShopTransaction> findByCustomerEmailOrderByCreatedAtDesc(String email);
// Generated SQL: SELECT * FROM shop_transactions WHERE customer_email = ? ORDER BY created_at DESC

// Count queries
long countByStatus(TransactionStatus status);
// Generated SQL: SELECT COUNT(*) FROM shop_transactions WHERE status = ?

// Check existence
boolean existsByTransactionId(String transactionId);
// Generated SQL: SELECT CASE WHEN COUNT(*) > 0 THEN true ELSE false END FROM shop_transactions WHERE transaction_id = ?
```

**Naming Convention Rules:**
- `findBy` + `FieldName` = WHERE clause
- `And` = Multiple conditions
- `Or` = Alternative conditions
- `OrderBy` + `FieldName` + `Asc/Desc` = Sorting
- `countBy` = COUNT query
- `existsBy` = Boolean check

### Method 2: JPQL Queries (Java Persistence Query Language)

For more complex queries, use `@Query` with JPQL:

```java
@Query("SELECT s FROM ShopTransaction s WHERE s.status = :status AND s.createdAt < :cutoffTime")
List<ShopTransaction> findStaleTransactionsByStatus(
    @Param("status") TransactionStatus status,
    @Param("cutoffTime") LocalDateTime cutoffTime
);
```

**JPQL Key Points:**
- Use entity class names (`ShopTransaction`), not table names
- Use field names (`createdAt`), not column names (`created_at`)
- Use `:paramName` for parameters
- Object-oriented syntax (no need to worry about SQL dialects)

### Method 3: Native SQL Queries

For database-specific functions or complex performance queries:

```java
@Query(value = "SELECT AVG(DATEDIFF(SECOND, created_at, cloud_confirmed_at)) " +
       "FROM shop_transactions WHERE status = 'COMPLETED' AND created_at >= :since", 
       nativeQuery = true)
Double getAverageProcessingTimeSeconds(@Param("since") LocalDateTime since);
```

**When to use Native SQL:**
- Database-specific functions (DATEDIFF, GETDATE, etc.)
- Complex aggregations
- Performance-critical queries
- When JPQL can't express what you need

**Important**: Set `nativeQuery = true` in the `@Query` annotation!

### Example: Adding a Complex Query

Let's add a query to find high-value transactions by store:

```java
@Query(value = """
    SELECT s.store_location, 
           COUNT(*) as transaction_count,
           AVG(s.total_amount) as avg_amount,
           MAX(s.total_amount) as max_amount
    FROM shop_transactions s
    WHERE s.created_at >= :since
      AND s.status = 'COMPLETED'
    GROUP BY s.store_location
    HAVING AVG(s.total_amount) > :minAverage
    ORDER BY AVG(s.total_amount) DESC
    """, nativeQuery = true)
List<Object[]> findHighValueStores(
    @Param("since") LocalDateTime since,
    @Param("minAverage") BigDecimal minAverage
);
```

**Note**: Use `List<Object[]>` for custom projections that don't map to entities.

---

## Testing Your Changes

### 1. Unit Testing Service Logic

Create test file: `src/test/java/com/opentelemetry/demo/shopdcshim/service/ShopTransactionServiceTest.java`

```java
@SpringBootTest
@Transactional
class ShopTransactionServiceTest {
    
    @Autowired
    private ShopTransactionService service;
    
    @Autowired
    private ShopTransactionRepository repository;
    
    @Test
    void testInitiateShopPurchase() {
        ShopPurchaseRequest request = createTestRequest();
        
        String transactionId = service.initiateShopPurchase(request);
        
        assertNotNull(transactionId);
        
        ShopTransaction saved = repository.findByTransactionId(transactionId).orElseThrow();
        assertEquals(request.getCustomerEmail(), saved.getCustomerEmail());
        assertEquals(ShopTransaction.TransactionStatus.INITIATED, saved.getStatus());
    }
}
```

### 2. Testing Database Queries

```java
@Test
void testFindByCustomerEmail() {
    // Create test data
    ShopTransaction tx = new ShopTransaction();
    tx.setTransactionId(UUID.randomUUID().toString());
    tx.setCustomerEmail("test@example.com");
    tx.setStatus(ShopTransaction.TransactionStatus.COMPLETED);
    repository.save(tx);
    
    // Test query
    List<ShopTransaction> results = repository.findByCustomerEmail("test@example.com");
    
    assertEquals(1, results.size());
    assertEquals("test@example.com", results.get(0).getCustomerEmail());
}
```

### 3. Integration Testing with curl

```bash
# Test POST endpoint
curl -X POST http://localhost:8070/api/shop/purchase \
  -H "Content-Type: application/json" \
  -d '{
    "customerName": "Test User",
    "customerEmail": "test@example.com",
    "totalAmount": 99.99,
    "currencyCode": "USD",
    "storeLocation": "DC-NYC-01",
    "terminalId": "TERM-001",
    "shippingAddress": {
      "streetAddress": "123 Test St",
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
        "productId": "OLJCESPC7Z",
        "quantity": 1,
        "unitPrice": 99.99,
        "productName": "Vintage Typewriter"
      }
    ]
  }'

# Get the transaction ID from response, then check status
curl http://localhost:8070/api/shop/transaction/{transactionId}

# Test stats endpoint
curl http://localhost:8070/api/shop/stats
```

### 4. Checking SQL Queries in Logs

Enable SQL logging in `application.properties`:

```properties
# Show generated SQL
spring.jpa.show-sql=true

# Format SQL nicely
spring.jpa.properties.hibernate.format_sql=true

# Show parameter values
logging.level.org.hibernate.type.descriptor.sql.BasicBinder=TRACE
```

Then check logs to see actual SQL:
```
Hibernate: 
    select
        st1_0.id,
        st1_0.cloud_confirmed_at,
        st1_0.cloud_order_id,
        ...
    from
        shop_transactions st1_0 
    where
        st1_0.transaction_id=?
```

---

## Debugging Tips

### 1. Trace Slow Queries

Use OpenTelemetry spans to identify slow operations:

```java
Span span = tracer.spanBuilder("custom_operation")
        .setAttribute("operation.type", "database")
        .startSpan();

try {
    // Your database operation
    List<ShopTransaction> results = repository.someExpensiveQuery();
    span.setAttribute("result.count", results.size());
} finally {
    span.end();  // Duration is automatically calculated
}
```

Then look in Splunk Observability or AppDynamics to see which operations are slowest.

### 2. Database Connection Issues

If you see errors like "Connection refused" or "Login timeout":

**Check database connectivity:**
```bash
# From inside the container
kubectl exec -it deployment/shop-dc-shim -- bash
telnet shop-dc-shim-db 1433

# Check connection string in logs
kubectl logs deployment/shop-dc-shim | grep "datasource.url"
```

**Check HikariCP pool:**
```properties
# Increase logging for connection pool
logging.level.com.zaxxer.hikari=DEBUG
```

### 3. Transaction Debugging

If transactions aren't saving or updates are lost:

**Check transaction boundaries:**
- Every method that modifies data needs `@Transactional`
- Read-only operations should use `@Transactional(readOnly = true)`
- Async methods (`@Async`) create new transactions

**Common mistake:**
```java
// BAD: This won't save because it's not transactional
public void updateStatus(String id) {
    ShopTransaction tx = repository.findById(id).orElseThrow();
    tx.setStatus(TransactionStatus.COMPLETED);
    // No save() call and no @Transactional means changes are lost!
}

// GOOD: Properly transactional
@Transactional
public void updateStatus(String id) {
    ShopTransaction tx = repository.findById(id).orElseThrow();
    tx.setStatus(TransactionStatus.COMPLETED);
    repository.save(tx);  // Explicitly save
}
```

### 4. Finding Which Query is Slow

Add timing logs:

```java
@Transactional(readOnly = true)
public List<ShopTransaction> getTransactionsByStore(String storeLocation, LocalDateTime since) {
    long start = System.currentTimeMillis();
    
    List<ShopTransaction> results = transactionRepository.findByStoreLocationAndCreatedAtAfter(storeLocation, since);
    
    long duration = System.currentTimeMillis() - start;
    log.info("Query took {} ms, returned {} results", duration, results.size());
    
    return results;
}
```

---

## Common Patterns

### Pattern 1: Adding a New DTO (Request/Response Object)

Create a new file in `dto/` package:

```java
package com.opentelemetry.demo.shopdcshim.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class StoreStatsRequest {
    @NotBlank(message = "Store location is required")
    private String storeLocation;
    
    private Integer hours = 24;  // Default value
}
```

### Pattern 2: Adding a New Entity Field

1. **Add field to Entity:**
```java
@Column(name = "discount_applied", precision = 10, scale = 2)
private BigDecimal discountApplied;
```

2. **Update schema.sql:**
```sql
ALTER TABLE shop_transactions ADD discount_applied DECIMAL(10,2);
```

3. **Hibernate can auto-update** (because `spring.jpa.hibernate.ddl-auto=update`), but schema.sql is documentation.

### Pattern 3: Handling Errors in Controllers

Always follow this pattern:

```java
try {
    // Your logic
    return ResponseEntity.ok(response);
    
} catch (SpecificException e) {
    // Handle specific errors
    span.setAttribute("http.status_code", 404);
    return ResponseEntity.notFound().build();
    
} catch (Exception e) {
    // Handle general errors
    span.recordException(e);
    span.setAttribute("http.status_code", 500);
    log.error("Error in operation", e);
    return ResponseEntity.internalServerError()
            .body(Map.of("error", "Internal server error", "message", e.getMessage()));
            
} finally {
    span.end();  // ALWAYS close span
}
```

### Pattern 4: Async Processing

For long-running operations, use async:

```java
@Async
@Transactional
public CompletableFuture<String> processInBackground(String id) {
    // This runs in a separate thread pool
    // Do expensive work here
    return CompletableFuture.completedFuture(result);
}
```

**Important**: Async methods must return `CompletableFuture<T>` or `void`.

---

## Quick Reference

### File Structure
```
src/main/java/com/opentelemetry/demo/shopdcshim/
├── ShopDcShimApplication.java        # Main entry point
├── config/
│   └── OpenTelemetryConfig.java      # OTel configuration
├── controller/
│   └── ShopController.java           # HTTP endpoints
├── dto/
│   └── ShopPurchaseRequest.java      # Request/response objects
├── entity/
│   └── ShopTransaction.java          # Database table mapping
├── repository/
│   └── ShopTransactionRepository.java # Database queries
└── service/
    ├── ShopTransactionService.java   # Business logic
    └── CloudCheckoutService.java     # gRPC client

src/main/resources/
├── application.properties             # Configuration
└── schema.sql                        # Database schema
```

### Annotation Quick Reference

| Annotation | Purpose | Where to Use |
|------------|---------|--------------|
| `@RestController` | Marks HTTP endpoint class | Controller classes |
| `@RequestMapping("/api/shop")` | Base URL path | Controller classes |
| `@GetMapping("/path")` | HTTP GET endpoint | Controller methods |
| `@PostMapping("/path")` | HTTP POST endpoint | Controller methods |
| `@PathVariable` | Extract URL parameter | Controller method parameters |
| `@RequestParam` | Extract query parameter | Controller method parameters |
| `@RequestBody` | Parse JSON body | Controller method parameters |
| `@Valid` | Enable validation | Before `@RequestBody` |
| `@Service` | Spring service bean | Service classes |
| `@Repository` | Spring repository bean | Repository interfaces |
| `@Entity` | JPA entity (table) | Entity classes |
| `@Table(name="...")` | Specify table name | Entity classes |
| `@Column(name="...")` | Specify column name | Entity fields |
| `@Transactional` | Database transaction | Service methods (writes) |
| `@Transactional(readOnly=true)` | Read-only transaction | Service methods (reads) |
| `@Async` | Run in background | Service methods |
| `@Scheduled` | Run periodically | Service methods |
| `@Query("...")` | Custom query | Repository methods |

---

## Next Steps

1. **Read the existing endpoints** in `ShopController.java` to understand the patterns
2. **Examine the queries** in `ShopTransactionRepository.java` to see different query styles
3. **Try adding a simple endpoint** like finding transactions by terminal ID
4. **Enable SQL logging** and observe what queries are generated
5. **Check OpenTelemetry traces** in Splunk Observability to see the full request flow

---

## Questions?

Common questions answered:

**Q: Why is `findByTransactionId()` so slow?**  
A: It's intentionally bad to demonstrate APM value! See `ShopTransactionRepository.java` lines 19-34.

**Q: When do I use `@Transactional`?**  
A: Always use it on service methods that modify data. Use `readOnly=true` for queries.

**Q: Why do some fields store JSON as strings?**  
A: It simplifies the schema and demonstrates legacy system patterns.

**Q: How do I know if my query is efficient?**  
A: Enable `spring.jpa.show-sql=true`, check logs, and use EXPLAIN in SQL Server.

**Q: Can I test without the full Kubernetes setup?**  
A: Yes, but you'll need a local SQL Server instance. Update `application.properties` with your local connection string.

---

Happy coding! 🚀



