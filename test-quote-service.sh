#!/bin/bash

# OpenTelemetry CF Demo - Quote Service Test Script
# Tests all CFM pages and runs comprehensive load test on removeoldquotes.cfm

set -e

QUOTE_URL="http://localhost:8888"
LOG_FILE="/tmp/quote-service-test-$(date +%Y%m%d-%H%M%S).log"

echo "=========================================="
echo "OpenTelemetry CF Demo - Quote Service Test"
echo "=========================================="
echo "Logging to: $LOG_FILE"
echo ""

# Function to log with timestamp
log_with_time() {
    echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Function to test a CFM page
test_cfm_page() {
    local page=$1
    local description=$2
    log_with_time "Testing $page ($description) - 5 requests:"
    
    local success=0
    local slow_count=0
    local total_time=0
    
    for i in {1..5}; do
        start_time=$(date +%s.%N)
        
        if response=$(curl -s --max-time 60 "$QUOTE_URL/$page" 2>/dev/null); then
            end_time=$(date +%s.%N)
            duration=$(echo "$end_time - $start_time" | bc -l)
            total_time=$(echo "$total_time + $duration" | bc -l)
            
            # Check if request was slow (>3 seconds)
            if (( $(echo "$duration > 3.0" | bc -l) )); then
                slow_count=$((slow_count + 1))
                log_with_time "  Request $i: ${duration}s (SLOW) - $(echo "$response" | head -1 | cut -c1-50)..."
            else
                log_with_time "  Request $i: ${duration}s - $(echo "$response" | head -1 | cut -c1-50)..."
            fi
            success=$((success + 1))
        else
            log_with_time "  Request $i: FAILED"
        fi
    done
    
    avg_time=$(echo "scale=3; $total_time / 5" | bc -l)
    log_with_time "  Results: $success/5 successful, $slow_count slow queries, avg time: ${avg_time}s"
    echo ""
}

# Warm up all CFM pages
log_with_time "=== WARMING UP ALL CFM PAGES ==="
echo ""

test_cfm_page "health.cfm" "Health check endpoint"
test_cfm_page "index.cfm" "Main index page"
test_cfm_page "getquote.cfm" "Get quote API (expects numberOfItems param)"
test_cfm_page "report.cfm" "Reporting page"
test_cfm_page "updatequote.cfm" "Update quote functionality"
test_cfm_page "debug.cfm" "Debug information page"
test_cfm_page "emailquote.cfm" "Email quote functionality"
test_cfm_page "removeoldquotes.cfm" "Database cleanup (may trigger slow query)"

# Comprehensive load test on removeoldquotes.cfm
log_with_time "=== COMPREHENSIVE LOAD TEST: removeoldquotes.cfm (200 requests) ==="
echo ""

success_count=0
slow_count=0
timeout_count=0
error_count=0
total_duration=0
slow_times=()
fast_times=()

log_with_time "Starting 200 consecutive requests..."

for i in {1..200}; do
    if [ $((i % 25)) -eq 0 ]; then
        log_with_time "Progress: $i/200 requests completed"
    fi
    
    start_time=$(date +%s.%N)
    
    if response=$(timeout 35s curl -s "$QUOTE_URL/removeoldquotes.cfm" 2>/dev/null); then
        end_time=$(date +%s.%N)
        duration=$(echo "$end_time - $start_time" | bc -l)
        total_duration=$(echo "$total_duration + $duration" | bc -l)
        
        success_count=$((success_count + 1))
        
        # Classify as slow if >3 seconds
        if (( $(echo "$duration > 3.0" | bc -l) )); then
            slow_count=$((slow_count + 1))
            slow_times+=("$duration")
            if [ $((i % 25)) -eq 0 ] || (( $(echo "$duration > 5.0" | bc -l) )); then
                log_with_time "  Request $i: ${duration}s (SLOW QUERY)"
            fi
        else
            fast_times+=("$duration")
        fi
    elif [ $? -eq 124 ]; then
        timeout_count=$((timeout_count + 1))
        log_with_time "  Request $i: TIMEOUT (>35s)"
    else
        error_count=$((error_count + 1))
        log_with_time "  Request $i: ERROR"
    fi
done

# Calculate statistics
avg_time=$(echo "scale=3; $total_duration / $success_count" | bc -l)
slow_percentage=$(echo "scale=1; $slow_count * 100 / 200" | bc -l)

# Calculate slow query average if any exist
if [ ${#slow_times[@]} -gt 0 ]; then
    slow_total=0
    for time in "${slow_times[@]}"; do
        slow_total=$(echo "$slow_total + $time" | bc -l)
    done
    avg_slow_time=$(echo "scale=3; $slow_total / ${#slow_times[@]}" | bc -l)
else
    avg_slow_time="N/A"
fi

# Calculate fast query average if any exist
if [ ${#fast_times[@]} -gt 0 ]; then
    fast_total=0
    for time in "${fast_times[@]}"; do
        fast_total=$(echo "$fast_total + $time" | bc -l)
    done
    avg_fast_time=$(echo "scale=3; $fast_total / ${#fast_times[@]}" | bc -l)
else
    avg_fast_time="N/A"
fi

log_with_time "All 200 requests completed!"
echo ""

# Final Results Summary
log_with_time "========================================"
log_with_time "          FINAL TEST RESULTS"
log_with_time "========================================"
log_with_time "Total Requests: 200"
log_with_time "Successful: $success_count"
log_with_time "Timeouts: $timeout_count"
log_with_time "Errors: $error_count"
log_with_time ""
log_with_time "Performance Analysis:"
log_with_time "- Slow queries (>3s): $slow_count (${slow_percentage}%)"
log_with_time "- Fast queries (<3s): $((success_count - slow_count))"
log_with_time "- Average response time: ${avg_time}s"
log_with_time "- Average slow query time: ${avg_slow_time}s"
log_with_time "- Average fast query time: ${avg_fast_time}s"
log_with_time ""

# Performance Assessment
if [ $timeout_count -eq 0 ] && [ $error_count -eq 0 ]; then
    if (( $(echo "$slow_percentage >= 3.0 && $slow_percentage <= 7.0" | bc -l) )); then
        log_with_time "✅ EXCELLENT: Perfect performance profile for demo!"
        log_with_time "   - No timeouts or errors"
        log_with_time "   - Slow query rate within target range (3-7%)"
        if [ "$avg_slow_time" != "N/A" ] && (( $(echo "$avg_slow_time >= 4.0 && $avg_slow_time <= 8.0" | bc -l) )); then
            log_with_time "   - Slow queries in optimal range (4-8s)"
        fi
    else
        log_with_time "⚠️  GOOD: System stable but slow query rate off target"
        log_with_time "   - Target: 5% slow queries, Actual: ${slow_percentage}%"
    fi
else
    log_with_time "❌ ISSUES DETECTED:"
    [ $timeout_count -gt 0 ] && log_with_time "   - $timeout_count requests timed out"
    [ $error_count -gt 0 ] && log_with_time "   - $error_count requests failed"
fi

log_with_time ""
log_with_time "Log file: $LOG_FILE"
log_with_time "========================================"

echo ""
echo "Test completed! Check the log file for detailed results:"
echo "$LOG_FILE"