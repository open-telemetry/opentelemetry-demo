#!/bin/sh
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# This script is used to start the demo.
# It can be used to start just the demo (no arguments), the full demo ("full" or "all" as the first argument),
# or any combination of the modules (e.g. "load observability" to start the load generator, and observability components.

# Usage: ./start-demo.sh [full|all|<module> ...]

run_full() {
  echo "Starting full demo..."
  docker compose -f docker-compose.full.yml up --force-recreate --remove-orphans --detach
  echo "Full demo started."
  print_how_to_use full
}

run_modules() {
  compose_files="-f docker-compose.yml "
  modules=""

  for i in "$@"; do
    if [ "$i" = "full" ] || [ "$i" = "all" ]; then
      echo "ERROR!"
      echo "Use \"$i\" without any other arguments to run the full demo."
      print_usage
      exit 1
    fi
    compose_files="$compose_files -f docker-compose.$i.yml"
    modules="$modules $i"
  done

  echo "Starting demo with modules:$modules"
  # shellcheck disable=SC2086
  docker compose $compose_files up --force-recreate --remove-orphans --detach
  echo "Demo started with modules:$modules"
  print_how_to_use "$@"
}

print_how_to_use() {
  echo
  echo "Go to http://localhost:8080 for the demo UI."

  if [ "$1" = "full" ] || [ "$1" = "all" ]; then
    echo "Go to http://localhost:8080/jaeger/ui for the Jaeger UI."
    echo "Go to http://localhost:8080/loadgen/ for the Load Generator UI."
    echo "Go to http://localhost:8080/feature/ for the Feature Flag UI."
    echo "Go to http://localhost:8080/grafana/ for the Grafana UI."

  else
    for i in "$@"; do
      case $i in
      featureflags)
        echo "Go to http://localhost:8080/feature/ for the Feature Flag UI."
        ;;
      kafka-extras) ;;
      load)
        echo "Go to http://localhost:8080/loadgen/ for the Load Generator UI."
        ;;
      observability)
        echo "Go to http://localhost:8080/jaeger/ui for the Jaeger UI."
        echo "Go to http://localhost:8080/grafana/ for the Grafana UI."
        ;;
      tests) ;;
      *)
        echo "Unknown module: $i"
        ;;
      esac
    done
  fi
}

check_args() {
  for i in "$@"; do
    if [ "$i" = "-h" ] || [ "$i" = "--help" ]; then
      print_usage
      exit 0
    else
      case $i in
      full | all | featureflags | kafka-extras | load | observability | tests) ;;
      *)
        echo "Unknown module: $i"
        print_usage
        exit 1
        ;;
      esac
    fi
  done
}

print_usage() {
  echo
  echo "Usage: ./start-demo.sh [full|all|<module> ...]"
  echo
}

check_args "$@"
if [ "$1" = "full" ] || [ "$1" = "all" ]; then
  run_full
else
  run_modules "$@"
fi
