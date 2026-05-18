# Correlating Tsuga Traces with Database Logs

This document describes how to propagate OpenTelemetry trace context from your
application into database logs, enabling automatic correlation between Tsuga
traces and database query logs using shared trace identifiers.

Tsuga is a unified observability backend for logs, traces, and metrics that
automatically correlates logs and traces based on trace ID, providing seamless
navigation between distributed traces and related log entries.

## Overview

When instrumenting applications with OpenTelemetry, each request receives a
unique trace ID (a 128-bit identifier) and span ID (a 64-bit identifier). By
injecting these identifiers into SQL statements as **comments**, you can
correlate:

1. **Tsuga traces**: trace and span metadata in your distributed tracing UI
2. **Database logs**: the same trace/span IDs embedded in logged SQL statements

With Tsuga's automatic correlation by trace ID, this enables powerful debugging
workflows:

- **Trace -> Database**: From a slow trace in Tsuga, automatically jump to the
  exact SQL queries and their execution details in database logs
- **Database -> Trace**: From an expensive query in database logs,
  automatically navigate to the full distributed trace in Tsuga showing the
  request context
- **Performance analysis**: Correlate query execution times seen in database
  logs with span durations in Tsuga traces
- **Troubleshooting**: Identify which application requests generated
  problematic queries

## Benefits

- **Automatic correlation**: Tsuga automatically links traces and logs by trace
  ID -- no manual correlation or separate log backend queries needed
- **Unified observability**: View application-level traces and database-level
  logs in a single platform
- **Seamless navigation**: Click through from traces to related logs and vice
  versa within Tsuga's UI
- **Root cause analysis**: Quickly identify whether performance issues
  originate in application logic or database queries
- **Query attribution**: Determine which services, endpoints, or user requests
  generated specific database queries
- **Compliance and auditing**: Track the full path of data access from user
  request through to database operations

## Architecture

```text
+-------------------------------------------------------------+
|  Instrumented Application (OpenTelemetry SDK)               |
|  - Active trace context: trace_id + span_id                 |
|  - Sqlcommenter library injects context into SQL comments   |
+------------------------------+------------------------------+
                               |                              |
                               | SQL with trace context       | OTLP spans
                               | (comment injected)         | (trace_id, span_id)
                               v                              |
+-------------------------------+                            |
|  PostgreSQL Database          |                            |
|  - log_statement=all          |                            |
|  - Logs SQL with comment      |                            |
|  - trace_id in log text       |                            |
+-------------------------------+                            |
                               |                              |
                               | DB logs with trace_id        |
                               | (stderr/syslog)              |
                               v                              v
              +------------------------------------------------+
              |  Tsuga (Unified Observability Backend)         |
              |  - Ingests logs, traces, and metrics           |
              |  - Automatically correlates logs & traces      |
              |    by trace_id                                 |
              |  - Jump from trace to related DB logs            |
              |  - Jump from DB logs to full trace               |
              +------------------------------------------------+
```

**Key components:**

1. **Application**: OpenTelemetry SDK provides trace context; sqlcommenter
   injects it into SQL
2. **Database**: Logs all statements including comments with trace/span IDs
3. **Tsuga**: Unified observability backend that automatically correlates logs
   and traces by trace ID, enabling seamless navigation between distributed
   traces and database logs

## How It Works

### Prerequisites

Before implementing trace-to-log correlation, ensure:

1. **OpenTelemetry instrumentation**: Your application has OpenTelemetry SDK
   configured with proper trace context propagation
2. **Active trace context**: Each request creates or propagates a trace context
   (automatic with OpenTelemetry auto-instrumentation)
3. **Database access**: Application uses a database client library that can be
   wrapped or extended
4. **Database logging**: Database server can log executed SQL statements

### 1. Application: Inject Trace Context into SQL

The application appends the current OpenTelemetry trace ID and span ID to each
SQL statement as a **SQL comment**. When the database executes and logs the
statement, the comment (containing trace identifiers) appears in the log.

#### SQL Comment Format

Sqlcommenter libraries typically generate comments in this format:

```sql
SELECT * FROM products WHERE id = 123
/*traceparent='00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01',
  db_driver='psycopg2%3A2.9.9'*/
```

The `traceparent` field follows the [W3C Trace Context][w3c-trace-context]
specification:

- Format: `version-trace_id-span_id-trace_flags`
- `trace_id`: 32-character hex string (128 bits)
- `span_id`: 16-character hex string (64 bits)
- `trace_flags`: 2-character hex string (sampling decision, etc.)

#### Implementation by Language

##### Python (psycopg2)

Use
[google-cloud-sqlcommenter](https://pypi.org/project/google-cloud-sqlcommenter/)
with a custom cursor factory:

```python
import psycopg2
from google.cloud.sqlcommenter.psycopg2.extension import CommenterCursorFactory

# Create cursor factory that automatically injects trace context
cursor_factory = CommenterCursorFactory(
    with_opentelemetry=True,  # Include trace_id and span_id from active context
    with_db_driver=True,      # Include driver version for debugging
    with_dbapi_level=False,   # Optional: include DB-API spec level
    with_dbapi_threadsafety=False  # Optional: include thread safety level
)

# Use the factory for all connections
connection = psycopg2.connect(
    host="localhost",
    database="productdb",
    user="dbuser",
    password="dbpass",
    cursor_factory=cursor_factory
)

# All queries now automatically include trace context in comments
with connection.cursor() as cursor:
    cursor.execute("SELECT * FROM products WHERE category = %s", ("electronics",))
    results = cursor.fetchall()
```

**Example generated SQL:**

```sql
SELECT * FROM products WHERE category = 'electronics'
/*traceparent='00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01',
  db_driver='psycopg2%3A2.9.9'*/
```

##### Python (SQLAlchemy)

For SQLAlchemy ORM:

```python
from sqlalchemy import create_engine, event
from google.cloud.sqlcommenter.sqlalchemy.executor import BeforeExecuteFactory

engine = create_engine("postgresql://user:pass@localhost/dbname")

# Attach sqlcommenter to engine events
event.listen(
    engine,
    "before_cursor_execute",
    BeforeExecuteFactory(with_opentelemetry=True),
    retval=True
)
```

##### Other Languages

- **Java**: Use [sqlcommenter-java](https://github.com/google/sqlcommenter)
  with Spring/Hibernate
- **Node.js**: Use [@google-cloud/sqlcommenter][npm-sqlcommenter] with Knex or
  Sequelize
- **Go**: Implement a custom driver wrapper or use middleware that injects
  comments
- **Ruby**: Use sqlcommenter-ruby with ActiveRecord

**Important considerations:**

- Apply the comment injection to **all database connections** used by your
  application
- Queries executed without the wrapper/factory will not have trace context
- Connection pooling: Ensure the cursor factory or wrapper is applied to all
  connections in the pool
- Read-only operations: Include trace context even for SELECT queries to
  correlate read performance

### 2. Database: Configure Statement Logging

The database must log executed SQL statements **including comments**. This
section covers PostgreSQL; other databases have similar capabilities.

#### PostgreSQL Configuration

**Key settings:**

```ini
# Log all executed statements (DDL, DML, queries)
log_statement = 'all'

# Where to send logs (stderr for container capture)
log_destination = 'stderr'

# Optional: Include query duration in logs
log_duration = on

# Optional: Include timestamp in logs
log_line_prefix = '%m [%p] %q%u@%d '

# Optional: Minimum query duration to log (0 = all)
log_min_duration_statement = 0
```

**Docker Compose example:**

```yaml
services:
  postgres:
    image: postgres:15
    command:
      - "postgres"
      - "-c"
      - "log_statement=all"
      - "-c"
      - "log_destination=stderr"
      - "-c"
      - "log_duration=on"
      - "-c"
      - "log_line_prefix=%m [%p] %q%u@%d "
    environment:
      POSTGRES_DB: productdb
      POSTGRES_USER: dbuser
      POSTGRES_PASSWORD: dbpass
```

**Kubernetes ConfigMap example:**

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: postgres-config
data:
  postgresql.conf: |
    log_statement = 'all'
    log_destination = 'stderr'
    log_duration = on
    log_line_prefix = '%m [%p] %q%u@%d '
```

#### Example Database Log Output

With the configuration above, PostgreSQL will produce logs like:

```text
2026-02-11 10:23:45.123 UTC [1234] user@productdb LOG:  duration: 2.145 ms  statement: SELECT * FROM products WHERE category = 'electronics'
/*traceparent='00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01',
  db_driver='psycopg2%3A2.9.9'*/
```

The trace ID `4bf92f3577b34da6a3ce929d0e0e4736` in the log will be automatically
extracted by your log collection pipeline and used by Tsuga to correlate this
database log with the corresponding distributed trace.

#### Performance Considerations

**Warning:** `log_statement=all` logs every SQL statement, which can:

- Generate significant log volume in high-throughput systems
- Increase I/O overhead (typically <5% for most workloads)
- Consume additional storage for log retention

**Mitigation strategies:**

- **Selective logging**: Use `log_min_duration_statement` to log only slow
  queries (e.g., `log_min_duration_statement = 100` for queries >100ms)
- **Sampling**: Implement application-level sampling (only inject comments for
  sampled traces)
- **Log rotation**: Configure aggressive log rotation to manage disk usage
- **Separate log volumes**: Store database logs on separate volumes to prevent
  log growth from affecting database performance

#### Other Databases

- **MySQL**: Enable general query log or slow query log with `log_output=FILE`
  or `log_output=TABLE`
- **Microsoft SQL Server**: Use Extended Events or SQL Profiler to capture
  statement execution
- **Oracle**: Enable SQL tracing with `ALTER SESSION SET SQL_TRACE=TRUE`
- **MongoDB**: Enable profiling with `db.setProfilingLevel(2)` to log all
  operations

### 3. Send Logs to Tsuga

To complete the correlation workflow, database logs should be sent to Tsuga
alongside your application traces.

#### Log Collection Configuration

**Automatic extraction with Tsuga's Postgres route:**

Tsuga provides a default route for PostgreSQL logs that automatically handles
trace and span ID extraction from database logs. The Postgres route applies
preprocessing (including grok parsing and remapping) to extract the `trace_id`
and `span_id` from SQL comments in the `traceparent` format.

To use this feature:

1. Configure your log shipper to send PostgreSQL logs to Tsuga
2. Apply the Postgres route to your database logs
3. Tsuga will automatically extract and index the trace and span IDs for
   correlation

**Manual configuration (if not using Tsuga's Postgres route):**

If you need custom log collection configuration:

- Extract the `trace_id` from the SQL comment to ensure it's indexed as a
  structured field
- Add appropriate labels (e.g., `service_name`, `log_type`) for filtering in
  Tsuga
- Send logs to Tsuga's ingestion endpoint

#### Automatic Correlation in Tsuga

Once both traces and logs are ingested into Tsuga with trace IDs:

1. **View a trace** in Tsuga UI
2. **Click on "Related Logs"** to see all database logs for that trace ID
3. **View database logs** and click on the trace ID to jump to the full
   distributed trace

No manual searching or correlation queries needed -- Tsuga automatically links
them by trace ID.

## Complete Workflow Example

### Scenario: Debugging a Slow Request

1. **User reports slow page load** for product listing page

2. **Find the trace in Tsuga**:
   - Search for the endpoint: `GET /products?category=electronics`
   - Identify slow trace: `4bf92f3577b34da6a3ce929d0e0e4736`
   - Notice a database span took 2.5 seconds

3. **View related database logs** (automatic in Tsuga):
   - Click **"View Related Logs"** in the trace view
   - Tsuga automatically shows all database logs with the same trace ID

4. **Examine the problematic query** in the correlated logs:

   ```text
   2026-02-11 10:23:45.123 UTC [1234] LOG: duration: 2543.21 ms
   statement: SELECT * FROM products WHERE category = 'electronics' AND status = 'active'
   /*traceparent='00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'*/
   ```

5. **Analyze the query**:
   - No index on `status` column
   - Full table scan on 10M rows
   - The database log shows the exact query that caused the slow span

6. **Fix**: Add composite index on `(category, status)`

7. **Verify**: After deploying the fix, check subsequent traces in Tsuga for
   improved duration

**Alternative workflow** (starting from logs):

1. **DBA notices expensive query** in database logs within Tsuga
2. **Click on the trace ID** in the log entry
3. **Tsuga automatically opens the full distributed trace**, showing:
   - Which service/endpoint triggered the query
   - Complete request context (headers, user info, etc.)
   - All related spans and their durations
   - Other queries and operations in the same request

## Best Practices

### Application Level

1. **Apply globally**: Configure sqlcommenter at the database connection
   factory level to ensure all queries are instrumented
2. **Use connection pooling wisely**: Ensure the comment injection is applied
   to the pool factory, not individual connections
3. **Monitor overhead**: Measure the performance impact of comment injection
   (typically <1ms per query)
4. **Consistent formatting**: Use the same sqlcommenter configuration across
   all services for uniform log parsing

### Database Level

1. **Structured logging**: Use `log_line_prefix` to include consistent metadata
   (timestamp, PID, user, database)
2. **Selective logging**: In production, consider logging only slow queries
   (`log_min_duration_statement`) or sampled queries
3. **Log rotation**: Configure rotation to prevent disk exhaustion
4. **Separate volumes**: Use dedicated volumes for logs to isolate I/O impact

### Tsuga Integration Level

1. **Send logs and traces to Tsuga**: Configure your application to send OTLP
   traces and database logs to Tsuga for automatic correlation
2. **Extract trace_id field**: Ensure log parsing extracts `trace_id` as a
   structured field so Tsuga can correlate automatically
3. **Retention alignment**: Configure consistent retention periods for logs and
   traces in Tsuga (typically 7-30 days)
4. **Leverage automatic correlation**: Use Tsuga's built-in trace <-> log
   navigation features to jump between correlated data
5. **Dashboards**: Create dashboards showing trace -> query correlation metrics
   and database performance

### Security Considerations

1. **Sensitive data**: SQL comments are logged in plain text; ensure passwords
   or sensitive data are not in query parameters
2. **Log access control**: Restrict access to database logs (they contain query
   patterns and data access patterns)
3. **PII**: Be cautious when logging all statements if queries contain
   personally identifiable information
4. **Audit trails**: Trace IDs in database logs create an audit trail of which
   requests accessed what data

## Troubleshooting

### Trace IDs Not Appearing in Database Logs or Tsuga Not Correlating

**Symptom**: Database logs don't contain trace IDs, or Tsuga doesn't show
related logs for a trace

**Possible causes:**

1. **Sqlcommenter not configured**: Verify cursor factory or event listener is
   applied

   ```python
   # Add debug logging to verify comment injection
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

2. **No active trace context**: OpenTelemetry SDK not initialized or no trace
   context in the execution thread

   ```python
   from opentelemetry import trace
   current_span = trace.get_current_span()
   print(f"Current span: {current_span}")  # Should not be INVALID_SPAN
   ```

3. **Database not logging statements**: Check PostgreSQL configuration

   ```sql
   SHOW log_statement;  -- Should return 'all'
   ```

4. **Comments stripped by proxy/middleware**: Some database proxies or load
   balancers strip comments
   - Check if comments reach the database by examining `pg_stat_statements`

5. **Trace ID not extracted as a field**: Tsuga requires `trace_id` as a
   structured field in logs
   - Verify your log parser extracts the trace ID from SQL comments
   - Check that logs in Tsuga have a `trace_id` field when viewing log details

6. **Logs not sent to Tsuga**: Ensure database logs are being shipped to Tsuga
   - Verify Vector/Fluentd/your log shipper is running and configured correctly
   - Check Tsuga UI for recent database logs

### Trace ID Mismatch Between Logs and Tsuga

**Symptom**: Trace IDs in logs don't match Tsuga traces

**Possible causes:**

1. **Format mismatch**: Ensure consistent trace ID format (hex, with or without
   dashes)
   - OpenTelemetry uses 32-char hex without dashes:
     `4bf92f3577b34da6a3ce929d0e0e4736`
   - Some systems use UUID format with dashes:
     `4bf92f35-77b3-4da6-a3ce-929d0e0e4736`

2. **Sampling mismatch**: Trace might be sampled out in one system but not the
   other
   - Ensure head-based sampling is configured consistently

3. **Clock skew**: Timestamp-based correlation might fail if clocks are skewed
   - Use NTP to synchronize clocks across systems

### Performance Degradation After Enabling Logging

**Symptom**: Database performance drops after enabling statement logging

**Solutions:**

1. **Log only slow queries**:

   ```ini
   log_statement = 'none'
   log_min_duration_statement = 100  # Only log queries >100ms
   ```

2. **Reduce log verbosity**:

   ```ini
   log_duration = off
   log_line_prefix = '%m [%p] '  # Minimal prefix
   ```

3. **Use faster log destination**:

   ```ini
   log_destination = 'stderr'  # Faster than syslog or CSV
   ```

4. **Implement sampling**: Only inject comments for sampled traces

   ```python
   from opentelemetry import trace

   current_span = trace.get_current_span()
   if current_span.get_span_context().trace_flags.sampled:
       # Use commenter cursor factory
       cursor = connection.cursor(cursor_factory=commenter_factory)
   else:
       # Use regular cursor (no comment injection)
       cursor = connection.cursor()
   ```

## Alternative Approaches

While SQL comments are the most common approach, there are alternatives:

### 1. OpenTelemetry Database Instrumentation

OpenTelemetry auto-instrumentation libraries automatically create spans for
database operations with trace context. However, these spans are in the
**application's trace**, not in the **database's logs**.

**Pros:**

- Automatic instrumentation
- No database configuration required
- Works with any database

**Cons:**

- Doesn't correlate with native database logs
- Can't see query details as logged by the database (e.g., actual execution
  plan, index usage)

### 2. Database Activity Monitoring (DAM) Tools

Enterprise database monitoring tools can correlate application traces with
database activity by intercepting network traffic or using database-level
tracing.

**Pros:**

- No application code changes required
- Can capture queries from multiple applications

**Cons:**

- Expensive enterprise tools
- May require database proxy deployment
- Potential performance overhead

### 3. Application-Level Query Logging

Log queries at the application level with trace IDs, separate from database
logs.

**Pros:**

- Full control over what's logged
- Can include application context (user ID, tenant ID, etc.)

**Cons:**

- Doesn't capture database-specific details (execution time, plan, locks)
- Requires maintaining separate logging infrastructure

**Recommendation**: Use SQL comments (sqlcommenter) as the primary approach for
comprehensive database-level correlation.

## References

### OpenTelemetry

- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [OpenTelemetry semantic conventions for databases][otel-db-semconv]
- [W3C Trace Context Specification](https://www.w3.org/TR/trace-context/)
- [OpenTelemetry Python SDK](https://opentelemetry.io/docs/languages/python/)

### Sqlcommenter

- [google-cloud-sqlcommenter on PyPI][pypi-sqlcommenter]
- [Sqlcommenter GitHub Repository](https://github.com/google/sqlcommenter)
- [Sqlcommenter and OpenTelemetry integration][sqlc-otel-blog]
- [Sqlcommenter for
  Java](https://github.com/google/sqlcommenter/tree/master/java)
- [Sqlcommenter for
  Node.js](https://github.com/google/sqlcommenter/tree/master/nodejs)

### Database Configuration

- [PostgreSQL logging configuration][pg-logging]
- [PostgreSQL log_statement][pg-log-statement]
- [PostgreSQL log_line_prefix][pg-log-line-prefix]
- [MySQL General Query
  Log](https://dev.mysql.com/doc/refman/8.0/en/query-log.html)

### Log Backends

- [Grafana Loki LogQL](https://grafana.com/docs/loki/latest/logql/)
- [Elasticsearch Query DSL][es-query-dsl]

[pypi-sqlcommenter]: https://pypi.org/project/google-cloud-sqlcommenter/
[w3c-trace-context]: https://www.w3.org/TR/trace-context/
[npm-sqlcommenter]: https://www.npmjs.com/package/@google-cloud/sqlcommenter
[sqlc-otel-blog]: https://cloud.google.com/blog/products/databases/sqlcommenter-merges-with-opentelemetry
[pg-logging]: https://www.postgresql.org/docs/current/runtime-config-logging.html
[pg-log-statement]: https://www.postgresql.org/docs/current/runtime-config-logging.html#GUC-LOG-STATEMENT
[pg-log-line-prefix]: https://www.postgresql.org/docs/current/runtime-config-logging.html#GUC-LOG-LINE-PREFIX
[es-query-dsl]: https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl.html
[otel-db-semconv]: https://opentelemetry.io/docs/specs/semconv/database/

## Glossary

- **Trace ID**: A unique 128-bit identifier assigned to a distributed trace,
  represented as a 32-character hexadecimal string
- **Span ID**: A unique 64-bit identifier for a single unit of work within a
  trace, represented as a 16-character hexadecimal string
- **Trace Context**: The propagated context containing trace ID, span ID, and
  trace flags as defined by W3C Trace Context specification
- **Traceparent**: The HTTP header and comment field name containing trace
  context in W3C format
- **Sqlcommenter**: A library that automatically appends trace context and
  other metadata as SQL comments
- **OTLP**: OpenTelemetry Protocol, used to transmit traces, metrics, and logs
  to Tsuga
- **Sampling**: The decision to record and export a trace, typically based on
  probabilistic or deterministic rules
- **Correlation**: The process of linking related data across different
  observability signals (traces, metrics, logs) using shared identifiers. Tsuga
  performs automatic correlation by matching trace IDs between traces and logs
- **Tsuga**: A unified observability backend for logs, traces, and metrics that
  automatically correlates logs and traces based on trace ID

## Summary

Correlating Tsuga traces with database logs through SQL comment injection
provides powerful debugging capabilities with automatic correlation:

1. **Inject trace context**: Use sqlcommenter to automatically append
   trace/span IDs to SQL statements
2. **Configure database logging**: Enable statement logging to capture queries
   with comments
3. **Send logs to Tsuga**: Configure log collection to extract trace IDs and
   send database logs to Tsuga
4. **Automatic correlation**: Tsuga automatically links traces and logs by
   trace ID -- navigate seamlessly between traces and related database logs

This approach enables unified observability in a single platform, faster root
cause analysis, and better understanding of your application's database
interactions.

**Key takeaway**: Tsuga's automatic correlation eliminates manual log searching.
The small overhead of SQL comment injection and statement logging is outweighed
by the significant improvement in debugging capabilities, seamless navigation
between traces and logs, and reduced mean time to resolution (MTTR) for
database-related issues.
