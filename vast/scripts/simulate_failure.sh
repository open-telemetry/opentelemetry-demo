#!/bin/bash
#
# Simulate infrastructure failures for testing the diagnostic and predictive alerts tools
#
# Usage:
#   ./simulate_failure.sh <action> <target> [options]
#
# Actions:
#   block      - Block connections/stop the service (hard failure - no telemetry)
#   unblock    - Restore connections/start the service
#   degrade    - Introduce performance degradation (slow queries, partial failures)
#   restore    - Remove degradation
#   inject     - Inject failures via otel-demo API
#   status     - Check current status
#
# Targets for block/unblock/degrade:
#   postgres  - PostgreSQL database
#   redis     - Redis cache
#   kafka     - Kafka message broker
#   <service> - Any docker compose service name
#
# Targets for inject (otel-demo API):
#   payment-failure    - Partial payment failures (10%, 25%, 50%, 75%, 90%, 100%)
#   slow-images        - Slow loading images (5sec, 10sec)
#   cart-failure       - Cart service failures
#   ad-failure         - Ad service failures
#   memory-leak        - Email service memory leak (1x, 10x, 100x, 1000x)
#   kafka-problems     - Kafka queue problems
#   recommendation-cache - Cache failures
#
# Examples:
#   # Hard failures (produces no telemetry - hard to detect)
#   ./simulate_failure.sh block postgres
#   ./simulate_failure.sh unblock postgres
#
#   # Degraded performance (produces telemetry patterns - detectable by root cause monitoring)
#   ./simulate_failure.sh degrade postgres slow        # Slow queries
#   ./simulate_failure.sh degrade postgres memory      # Memory pressure
#   ./simulate_failure.sh restore postgres
#
#   # Inject application failures via otel-demo API
#   ./simulate_failure.sh inject payment-failure 50%   # 50% payment failures
#   ./simulate_failure.sh inject slow-images 5sec
#   ./simulate_failure.sh inject memory-leak 100x
#   ./simulate_failure.sh inject payment-failure off   # Restore
#

set -e

ACTION=${1:-status}
TARGET=${2:-postgres}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# PostgreSQL specific functions
postgres_block() {
    log_info "Blocking PostgreSQL connections..."
    docker compose exec -T postgresql psql -U root -d "${POSTGRES_DB:-otel}" -c \
        "REVOKE CONNECT ON DATABASE ${POSTGRES_DB:-otel} FROM PUBLIC;" 2>/dev/null || true

    log_info "Terminating existing connections..."
    docker compose exec -T postgresql psql -U root -d "${POSTGRES_DB:-otel}" -c \
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${POSTGRES_DB:-otel}' AND pid <> pg_backend_pid();" 2>/dev/null || true

    log_info "PostgreSQL connections blocked. Services will fail to connect."
}

postgres_unblock() {
    log_info "Restoring PostgreSQL connections..."
    docker compose exec -T postgresql psql -U root -d "${POSTGRES_DB:-otel}" -c \
        "GRANT CONNECT ON DATABASE ${POSTGRES_DB:-otel} TO PUBLIC;" 2>/dev/null || true

    log_info "PostgreSQL connections restored."
}

postgres_status() {
    log_info "Checking PostgreSQL status..."

    # Check if the PostgreSQL container is running
    PG_CONTAINER=$(timeout 5 docker ps --filter "name=postgresql" --filter "status=running" -q 2>/dev/null | head -1)

    if [ -z "$PG_CONTAINER" ]; then
        echo -e "PostgreSQL: ${RED}DOWN${NC} (container not running)"
        return
    fi

    echo -e "PostgreSQL: ${GREEN}CONTAINER RUNNING${NC}"

    # Check if the latency proxy is active
    PROXY_RUNNING=$(docker ps --filter "name=$PROXY_CONTAINER_NAME" --filter "status=running" -q 2>/dev/null)
    if [ -n "$PROXY_RUNNING" ]; then
        echo -e "Latency proxy: ${YELLOW}ACTIVE${NC} (${PROXY_LATENCY_MS}ms delay)"
        echo -e "  Services connect via: proxy → postgresql-direct"
    else
        echo -e "Latency proxy: ${GREEN}INACTIVE${NC} (direct connection)"
    fi

    # Measure actual query latency by connecting THROUGH the network
    # If proxy is active, this measures proxy + PostgreSQL latency
    # Uses another container to connect to 'postgresql' hostname (which hits proxy if active)
    echo -n "Measuring query latency... "

    # Find a container to probe from (any running otel-demo container)
    PROBE=$(docker ps --filter "status=running" -q 2>/dev/null | while read cid; do
        CNAME=$(docker inspect -f '{{.Name}}' "$cid" 2>/dev/null)
        # Skip the proxy itself and postgresql
        if echo "$CNAME" | grep -qvE "(postgresql|$PROXY_CONTAINER_NAME)"; then
            echo "$cid"
            break
        fi
    done)

    if [ -n "$PROBE" ]; then
        # Measure TCP connection time to 'postgresql:5432' from another container
        LATENCY=$(timeout 15 docker exec "$PROBE" sh -c '
            S=$(date +%s%N 2>/dev/null)
            if [ -z "$S" ] || [ "$S" = "0" ]; then exit 1; fi
            (echo > /dev/tcp/postgresql/5432) 2>/dev/null
            E=$(date +%s%N)
            echo $(( (E - S) / 1000000 ))
        ' 2>/dev/null)
        PROBE_EXIT=$?

        if [ $PROBE_EXIT -eq 0 ] && [ -n "$LATENCY" ]; then
            if [ "$LATENCY" -gt 500 ]; then
                echo -e "${RED}${LATENCY} ms${NC} (severely degraded)"
            elif [ "$LATENCY" -gt 50 ]; then
                echo -e "${YELLOW}${LATENCY} ms${NC} (degraded - normal is <5ms)"
            else
                echo -e "${GREEN}${LATENCY} ms${NC}"
            fi
        elif [ $PROBE_EXIT -eq 124 ]; then
            echo -e "${RED}TIMEOUT (>15s)${NC}"
        else
            echo -e "${YELLOW}could not measure${NC}"
        fi
    else
        echo -e "${YELLOW}no probe container found${NC}"
    fi
}

# PostgreSQL degradation functions (produces telemetry patterns)
postgres_degrade() {
    MODE=${3:-slow}
    case "$MODE" in
        slow)
            postgres_degrade_slow
            ;;
        memory)
            postgres_degrade_memory
            ;;
        *)
            log_error "Unknown degradation mode: $MODE (use 'slow' or 'memory')"
            exit 1
            ;;
    esac
}

PROXY_CONTAINER_NAME="pg-latency-proxy"
PROXY_STATE_FILE="/tmp/pg_proxy_active"
PROXY_LATENCY_MS=${PG_PROXY_LATENCY_MS:-150}

postgres_degrade_slow() {
    log_info "Enabling slow query simulation via TCP proxy..."

    # Find the PostgreSQL container and its Docker network
    PG_CONTAINER=$(docker ps --filter "name=postgresql" --filter "status=running" -q 2>/dev/null | head -1)
    if [ -z "$PG_CONTAINER" ]; then
        log_error "PostgreSQL container is not running"
        exit 1
    fi

    # Get the Docker network the PostgreSQL container is on
    PG_NETWORK=$(docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}' "$PG_CONTAINER" 2>/dev/null | head -1)
    if [ -z "$PG_NETWORK" ]; then
        log_error "Could not determine PostgreSQL container network"
        exit 1
    fi

    log_info "PostgreSQL container: $PG_CONTAINER"
    log_info "Docker network: $PG_NETWORK"

    # Remove existing proxy if any
    docker rm -f "$PROXY_CONTAINER_NAME" 2>/dev/null || true

    # Step 1: Disconnect PostgreSQL from the network and reconnect with a different alias
    # This makes the original 'postgresql' DNS name available for our proxy
    log_info "Rerouting PostgreSQL DNS via proxy..."

    # Get current aliases
    PG_ALIASES=$(docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{range $v.Aliases}}{{.}} {{end}}{{end}}' "$PG_CONTAINER" 2>/dev/null)
    log_info "Current aliases: $PG_ALIASES"

    docker network disconnect "$PG_NETWORK" "$PG_CONTAINER" 2>/dev/null || true
    docker network connect --alias postgresql-direct "$PG_NETWORK" "$PG_CONTAINER"

    # Step 2: Start the proxy container with alias 'postgresql'
    # Uses socat to forward TCP traffic, with a delay injected via tc netem on the proxy itself
    log_info "Starting latency proxy (${PROXY_LATENCY_MS}ms delay)..."

    docker run -d \
        --name "$PROXY_CONTAINER_NAME" \
        --network "$PG_NETWORK" \
        --network-alias postgresql \
        --cap-add NET_ADMIN \
        alpine/socat \
        TCP-LISTEN:5432,fork,reuseaddr TCP:postgresql-direct:5432

    # Wait for proxy to start
    sleep 2

    # Add network latency to the PROXY container (not PostgreSQL)
    # This is safe - docker exec to the proxy works fine since the proxy is just forwarding
    PROXY_ID=$(docker ps --filter "name=$PROXY_CONTAINER_NAME" -q 2>/dev/null)
    if [ -n "$PROXY_ID" ]; then
        docker exec --user root "$PROXY_ID" sh -c "
            apk add --quiet --no-cache iproute2 2>/dev/null
            tc qdisc add dev eth0 root netem delay ${PROXY_LATENCY_MS}ms 25ms 2>/dev/null || \
            tc qdisc change dev eth0 root netem delay ${PROXY_LATENCY_MS}ms 25ms 2>/dev/null
        " 2>/dev/null

        # Save state
        echo "${PG_NETWORK}" > "$PROXY_STATE_FILE"

        log_info "Proxy started successfully."
        log_info "All services now connect through proxy with ${PROXY_LATENCY_MS}ms +/- 25ms latency."
        log_info "PostgreSQL itself is unaffected (docker exec still works)."
        log_info "This should trigger 'DB_SLOW_QUERIES' alerts in root cause monitoring."
    else
        log_error "Proxy container failed to start. Restoring direct connection..."
        docker network disconnect "$PG_NETWORK" "$PG_CONTAINER" 2>/dev/null || true
        docker network connect --alias postgresql "$PG_NETWORK" "$PG_CONTAINER"
        exit 1
    fi
}

postgres_degrade_memory() {
    log_info "Simulating PostgreSQL memory pressure..."

    # Reduce shared_buffers and work_mem to create memory pressure
    docker compose exec -T postgresql psql -U root -d "${POSTGRES_DB:-otel}" <<'EOF'
-- Reduce work memory to create pressure
ALTER SYSTEM SET work_mem = '512kB';
ALTER SYSTEM SET maintenance_work_mem = '16MB';

-- Increase temp_buffers to consume memory differently
ALTER SYSTEM SET temp_buffers = '32MB';

SELECT pg_reload_conf();

-- Create a table to consume shared memory
CREATE TABLE IF NOT EXISTS _memory_pressure (
    id SERIAL PRIMARY KEY,
    data TEXT
);

-- Fill it with some data
INSERT INTO _memory_pressure (data)
SELECT repeat('x', 10000) FROM generate_series(1, 1000);
EOF

    log_info "Memory pressure simulation enabled."
    log_info "PostgreSQL is now running with reduced memory settings."
}

postgres_restore() {
    log_info "Restoring PostgreSQL to normal operation..."

    # Remove the proxy and restore direct PostgreSQL connection
    if [ -f "$PROXY_STATE_FILE" ]; then
        PG_NETWORK=$(cat "$PROXY_STATE_FILE")
        log_info "Removing latency proxy on network: $PG_NETWORK"

        # Find the real PostgreSQL container (connected as postgresql-direct)
        PG_CONTAINER=$(docker ps --filter "status=running" -q 2>/dev/null | while read cid; do
            if docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{range $v.Aliases}}{{.}} {{end}}{{end}}' "$cid" 2>/dev/null | grep -q "postgresql-direct"; then
                echo "$cid"
                break
            fi
        done)

        # Stop and remove the proxy container
        docker rm -f "$PROXY_CONTAINER_NAME" 2>/dev/null || true

        # Reconnect PostgreSQL with its original alias
        if [ -n "$PG_CONTAINER" ] && [ -n "$PG_NETWORK" ]; then
            log_info "Restoring direct PostgreSQL connection..."
            docker network disconnect "$PG_NETWORK" "$PG_CONTAINER" 2>/dev/null || true
            docker network connect --alias postgresql --alias postgresql-direct "$PG_NETWORK" "$PG_CONTAINER"
            log_info "PostgreSQL DNS alias restored."
        else
            log_warn "Could not find PostgreSQL container to restore alias."
            log_warn "You may need to restart the otel-demo: docker compose restart postgresql"
        fi

        rm -f "$PROXY_STATE_FILE"
    else
        # Legacy cleanup: remove tc netem if it was applied directly
        CONTAINER_ID=$(docker ps --filter "name=postgresql" -q 2>/dev/null)
        if [ -n "$CONTAINER_ID" ]; then
            timeout 10 docker exec --user root "$CONTAINER_ID" sh -c '
                tc qdisc del dev eth0 root 2>/dev/null || true
            ' 2>/dev/null || true
        fi
        docker rm -f "$PROXY_CONTAINER_NAME" 2>/dev/null || true
        rm -f /tmp/postgres_netem_active
    fi

    # Clean up memory pressure settings if any
    docker compose exec -T postgresql psql -U root -d "${POSTGRES_DB:-otel}" <<'EOF' 2>/dev/null
ALTER SYSTEM RESET work_mem;
ALTER SYSTEM RESET maintenance_work_mem;
ALTER SYSTEM RESET temp_buffers;
ALTER SYSTEM RESET effective_cache_size;
SELECT pg_reload_conf();
DROP TABLE IF EXISTS _memory_pressure;
EOF

    log_info "PostgreSQL restored to normal operation."
}

# Redis specific functions
redis_block() {
    log_info "Pausing Redis container..."
    docker compose pause redis 2>/dev/null || docker compose pause valkey-cart 2>/dev/null || {
        log_error "Could not find Redis container (tried 'redis' and 'valkey-cart')"
        exit 1
    }
    log_info "Redis paused. Services will timeout on Redis operations."
}

redis_unblock() {
    log_info "Unpausing Redis container..."
    docker compose unpause redis 2>/dev/null || docker compose unpause valkey-cart 2>/dev/null || {
        log_error "Could not find Redis container"
        exit 1
    }
    log_info "Redis restored."
}

redis_status() {
    log_info "Checking Redis status..."
    # Try both common redis container names
    for name in redis valkey-cart; do
        STATUS=$(docker compose ps --format json 2>/dev/null | grep -o "\"$name\"[^}]*" | head -1)
        if [ -n "$STATUS" ]; then
            if echo "$STATUS" | grep -q "paused"; then
                echo -e "Redis ($name): ${YELLOW}PAUSED${NC}"
            elif echo "$STATUS" | grep -q "running"; then
                echo -e "Redis ($name): ${GREEN}RUNNING${NC}"
            else
                echo -e "Redis ($name): ${RED}DOWN${NC}"
            fi
            return
        fi
    done
    echo -e "Redis: ${RED}NOT FOUND${NC}"
}

# =============================================================================
# otel-demo API injection functions
# =============================================================================

OTEL_DEMO_HOST=${OTEL_DEMO_HOST:-localhost}
OTEL_DEMO_PORT=${OTEL_DEMO_PORT:-8080}
OTEL_DEMO_ADMIN_URL="http://${OTEL_DEMO_HOST}:${OTEL_DEMO_PORT}/feature"

inject_failure() {
    FAILURE_TYPE=$2
    VALUE=${3:-on}

    # Map friendly names to otel-demo API method names
    case "$FAILURE_TYPE" in
        payment-failure|payment)
            METHOD="paymentServiceFailure"
            # Convert percentage to otel-demo format
            case "$VALUE" in
                off)   VALUE="0" ;;
                10%)   VALUE="10" ;;
                25%)   VALUE="25" ;;
                50%)   VALUE="50" ;;
                75%)   VALUE="75" ;;
                90%)   VALUE="90" ;;
                100%|on) VALUE="100" ;;
            esac
            ;;
        slow-images|slow-image)
            METHOD="imageSlowLoad"
            # Convert to otel-demo format
            case "$VALUE" in
                off)   VALUE="0" ;;
                5sec)  VALUE="5000" ;;
                10sec) VALUE="10000" ;;
            esac
            ;;
        cart-failure|cart)
            METHOD="cartServiceFailure"
            case "$VALUE" in
                off) VALUE="0" ;;
                on)  VALUE="1" ;;
            esac
            ;;
        ad-failure|ad)
            METHOD="adServiceFailure"
            case "$VALUE" in
                off) VALUE="0" ;;
                on)  VALUE="1" ;;
            esac
            ;;
        memory-leak|memleak)
            METHOD="recommendationServiceCacheFailure"
            # This causes recommendation service to consume memory
            case "$VALUE" in
                off)    VALUE="0" ;;
                1x)     VALUE="1" ;;
                10x)    VALUE="10" ;;
                100x)   VALUE="100" ;;
                1000x)  VALUE="1000" ;;
                10000x) VALUE="10000" ;;
            esac
            ;;
        kafka-problems|kafka-queue)
            METHOD="kafkaQueueProblems"
            case "$VALUE" in
                off) VALUE="0" ;;
                on)  VALUE="1" ;;
            esac
            ;;
        recommendation-cache|rec-cache)
            METHOD="recommendationServiceCacheFailure"
            case "$VALUE" in
                off) VALUE="0" ;;
                on)  VALUE="1" ;;
            esac
            ;;
        product-failure|product)
            METHOD="productCatalogFailure"
            case "$VALUE" in
                off) VALUE="0" ;;
                on)  VALUE="1" ;;
            esac
            ;;
        *)
            log_error "Unknown failure type: $FAILURE_TYPE"
            echo "Available types: payment-failure, slow-images, cart-failure, ad-failure,"
            echo "                 memory-leak, kafka-problems, recommendation-cache, product-failure"
            exit 1
            ;;
    esac

    log_info "Injecting failure via otel-demo API: $METHOD=$VALUE"

    # Call the otel-demo feature flag API
    RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
        "${OTEL_DEMO_ADMIN_URL}/${METHOD}/${VALUE}" \
        -H "Content-Type: application/json" 2>/dev/null || echo "error")

    HTTP_CODE=$(echo "$RESPONSE" | tail -1)
    BODY=$(echo "$RESPONSE" | head -n -1)

    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "204" ]; then
        log_info "Successfully set $METHOD=$VALUE"
        if [ "$VALUE" = "0" ] || [ "$VALUE" = "off" ]; then
            echo -e "Failure injection: ${GREEN}DISABLED${NC}"
        else
            echo -e "Failure injection: ${YELLOW}ACTIVE${NC} ($METHOD=$VALUE)"
        fi
    else
        log_warn "Could not reach otel-demo API at $OTEL_DEMO_ADMIN_URL"
        log_warn "HTTP $HTTP_CODE: $BODY"
        log_info "Make sure otel-demo is running and OTEL_DEMO_HOST/OTEL_DEMO_PORT are set correctly"
    fi
}

inject_status() {
    log_info "Checking otel-demo feature flags..."

    RESPONSE=$(curl -s "${OTEL_DEMO_ADMIN_URL}" 2>/dev/null || echo "error")

    if [ "$RESPONSE" = "error" ]; then
        log_warn "Could not reach otel-demo API at $OTEL_DEMO_ADMIN_URL"
        return
    fi

    echo "$RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    for key, value in data.items():
        if value and value != '0' and value != 0:
            print(f'  {key}: \033[1;33mACTIVE\033[0m ({value})')
        else:
            print(f'  {key}: inactive')
except:
    print('Could not parse response')
" 2>/dev/null || echo "  (Could not parse feature flag status)"
}

# =============================================================================
# Generic service functions (stop/start)
# =============================================================================

service_block() {
    log_info "Stopping $TARGET..."
    docker compose stop "$TARGET"
    log_info "$TARGET stopped."
}

service_unblock() {
    log_info "Starting $TARGET..."
    docker compose start "$TARGET"
    log_info "$TARGET started."
}

service_status() {
    log_info "Checking $TARGET status..."
    STATUS=$(docker compose ps "$TARGET" --format "{{.Status}}" 2>/dev/null)
    if [ -z "$STATUS" ]; then
        echo -e "$TARGET: ${RED}NOT FOUND${NC}"
    elif echo "$STATUS" | grep -qi "up"; then
        echo -e "$TARGET: ${GREEN}RUNNING${NC}"
    elif echo "$STATUS" | grep -qi "paused"; then
        echo -e "$TARGET: ${YELLOW}PAUSED${NC}"
    else
        echo -e "$TARGET: ${RED}DOWN${NC} ($STATUS)"
    fi
}

# =============================================================================
# Main logic
# =============================================================================

# Handle 'inject' action separately (works differently)
if [ "$ACTION" = "inject" ]; then
    if [ -z "$TARGET" ] || [ "$TARGET" = "status" ]; then
        inject_status
    else
        inject_failure "$ACTION" "$TARGET" "$3"
    fi
    echo ""
    log_info "Done. Wait 30-60 seconds for effects to propagate."
    log_info "Check the Predictive Alerts page for root cause detection."
    exit 0
fi

# Handle infrastructure targets
case "$TARGET" in
    postgres|postgresql)
        case "$ACTION" in
            block)   postgres_block ;;
            unblock) postgres_unblock ;;
            degrade) postgres_degrade "$@" ;;
            restore) postgres_restore ;;
            status)  postgres_status ;;
            *)       log_error "Unknown action: $ACTION"; exit 1 ;;
        esac
        ;;
    redis|valkey|valkey-cart)
        case "$ACTION" in
            block)   redis_block ;;
            unblock) redis_unblock ;;
            status)  redis_status ;;
            *)       log_error "Unknown action: $ACTION (redis only supports block/unblock/status)"; exit 1 ;;
        esac
        ;;
    *)
        # Generic service handling
        case "$ACTION" in
            block)   service_block ;;
            unblock) service_unblock ;;
            status)  service_status ;;
            *)       log_error "Unknown action: $ACTION"; exit 1 ;;
        esac
        ;;
esac

echo ""
log_info "Done. Wait 30-60 seconds for effects to propagate."
echo ""
echo "Root cause monitoring should detect:"
case "$ACTION" in
    degrade)
        echo "  - DB_SLOW_QUERIES: Database query latency increased"
        echo "  - Possibly ERROR_SPIKE if queries start timing out"
        ;;
    block)
        echo "  - DB_CONNECTION_FAILURE: Database connection errors"
        echo "  - DEPENDENCY_FAILURE: Downstream services failing"
        echo "  - SERVICE_DOWN: If telemetry stops completely"
        ;;
    inject)
        echo "  - DEPENDENCY_FAILURE: Service call failures"
        echo "  - LATENCY_DEGRADATION: Slow service responses"
        echo "  - EXCEPTION_SURGE: Increased exception rates"
        ;;
esac
echo ""
log_info "Check the Predictive Alerts page for root cause detection."
