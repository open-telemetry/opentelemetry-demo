#!/bin/sh

host="$1"
port="$2"
shift
shift
cmd="$@"

until nc -z -v -w30 "$host" "$port"; do
  echo "Waiting for service at $host:$port..."
  sleep 2
done

echo "Service is up and ready! Executing command:"
# create datasource for prometheus
echo "create datasource for prometheus"
exec $cmd

# create index template for logs,traces,metrics
echo "create index template for logs,traces,metrics,serviceMaps"
exec $cmd

# create data-streams for logs,traces,metrics
echo "create data-streams for logs,traces,metrics"
exec $cmd

# create email channel for alerting
echo " create email channel for alerting"
exec $cmd

# create saves searches for services KPI
echo " create saves searches for services KPI"
exec $cmd

# create Alerts queries for monitoring services
echo " create Alerts queries for monitoring services
exec $cmd

