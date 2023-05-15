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
echo "importing assets into opensearch"
exec $cmd
