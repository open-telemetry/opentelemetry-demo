#!/usr/bin/env bash
# Chaos case 1: product-catalog runs out of memory.
#
# product-catalog answers ListProducts with every row of catalog.products, built in memory
# on each call (no LIMIT), and the frontend home page calls it on every visit. Growing the
# table with stub rows makes each call allocate more until the pod passes its memory limit,
# is OOM-killed, restarts, and is killed again on the next requests: a repeating outage.
#
# Stub rows are marked so they are never mistaken for real products:
#   id   STUB-000001 ...
#   name [STUB] Load test product 1 ...
#   categories stub
#
# Usage:
#   ./product-catalog-memory.sh status                  rows, pod memory, restarts
#   ./product-catalog-memory.sh load [batch] [seconds] [max]
#                                                       add stub rows gradually (default 250 rows
#                                                       every 20s, up to 20000); Ctrl-C to stop
#   ./product-catalog-memory.sh loadgen <users>          set load-generator users (default demo: 5)
#   ./product-catalog-memory.sh limit <Mi> [gomemlimit]  set product-catalog memory limit and Go's
#                                                       soft limit (default demo: 32Mi / 16MiB)
#   ./product-catalog-memory.sh watch                   pod memory and restarts every 10s
#   ./product-catalog-memory.sh clean                   delete every stub row
#   ./product-catalog-memory.sh reset                   clean, 5 load-generator users, 32Mi / 16MiB
#
# Needs kubectl pointed at the otel-demo AKS cluster:
#   az aks get-credentials -g otel-demo-rg -n otel-demo-aks
# Note: astronomy-db keeps no data volume, so restarting that pod also removes the stub rows.

set -euo pipefail

NAMESPACE=otel-demo
CLUSTER=otel-demo-aks

context=$(kubectl config current-context)
if [[ "$context" != *"$CLUSTER"* && -z "${FORCE:-}" ]]; then
  echo "kubectl context is '$context', not $CLUSTER. Switch context, or set FORCE=1." >&2
  exit 1
fi

psql_db() {
  kubectl -n "$NAMESPACE" exec deploy/astronomy-db -- psql -U postgres -d astronomy_db -v ON_ERROR_STOP=1 -Atc "$1"
}

stub_count() {
  psql_db "select count(*) from catalog.products where id like 'STUB-%';"
}

status() {
  echo "catalog.products: $(psql_db "select count(*) from catalog.products;") rows ($(stub_count) stub)"
  local limit memory
  limit=$(kubectl -n "$NAMESPACE" get deploy product-catalog -o jsonpath='{.spec.template.spec.containers[0].resources.limits.memory}')
  # metrics-server has no sample for a container that keeps getting killed
  memory=$(kubectl -n "$NAMESPACE" top pod -l app.kubernetes.io/name=product-catalog --no-headers 2>/dev/null | awk '{print $3}') || true
  echo "product-catalog memory: ${memory:-no sample (container restarting)} (limit $limit)"
  kubectl -n "$NAMESPACE" get pod -l app.kubernetes.io/name=product-catalog \
    -o jsonpath='{range .items[*]}{.metadata.name}{"  restarts="}{.status.containerStatuses[0].restartCount}{"  last="}{.status.containerStatuses[0].lastState.terminated.reason}{"\n"}{end}'
}

# insert_stubs FROM TO adds STUB-<FROM..TO>; pictures cycle through the real product images
# so the frontend renders them without broken images.
insert_stubs() {
  psql_db "
    insert into catalog.products (id, name, description, picture, price_currency_code, price_units, price_nanos, categories)
    select 'STUB-' || lpad(g::text, 6, '0'),
           '[STUB] Load test product ' || g,
           repeat('Stub record for the product-catalog memory chaos demo; not a real product. ', 20),
           (array['NationalParkFoundationExplorascope.jpg','StarsenseExplorer.jpg','EclipsmartTravelRefractorTelescope.jpg',
                  'LensCleaningKit.jpg','RoofBinoculars.jpg','SolarSystemColorImager.jpg','RedFlashlight.jpg',
                  'OpticalTubeAssembly.jpg','SolarFilter.jpg','TheCometBook.jpg'])[1 + g % 10],
           'USD', 10 + g % 90, 0, 'stub'
    from generate_series($1, $2) g
    on conflict (id) do nothing;"
}

load() {
  local batch=${1:-250} interval=${2:-20} max=${3:-20000}
  local next=$(( $(psql_db "select coalesce(max(substr(id, 6)::int), 0) from catalog.products where id like 'STUB-%';") + 1 ))
  echo "adding $batch stub rows every ${interval}s from STUB-$(printf %06d "$next") up to $max stub rows; Ctrl-C to stop"
  while (( next <= max )); do
    local last=$(( next + batch - 1 ))
    (( last > max )) && last=$max
    insert_stubs "$next" "$last" >/dev/null
    echo "--- $(date +%H:%M:%S)  stub rows: $last"
    status | tail -n +2
    next=$(( last + 1 ))
    sleep "$interval"
  done
}

case "${1:-status}" in
  status) status ;;
  load) shift; load "$@" ;;
  loadgen)
    users=${2:?usage: loadgen <users>}
    kubectl -n "$NAMESPACE" set env deploy/load-generator LOCUST_USERS="$users"
    echo "load-generator restarting with $users users"
    ;;
  limit)
    mi=${2:?usage: limit <Mi> [gomemlimit-MiB]}
    gomem=${3:-$(( mi * 3 / 4 ))}
    kubectl -n "$NAMESPACE" set resources deploy/product-catalog --limits=memory="${mi}Mi"
    kubectl -n "$NAMESPACE" set env deploy/product-catalog GOMEMLIMIT="${gomem}MiB"
    kubectl -n "$NAMESPACE" rollout status deploy/product-catalog --timeout=180s
    ;;
  watch) while true; do echo "--- $(date +%H:%M:%S)"; status; sleep 10; done ;;
  clean)
    psql_db "delete from catalog.products where id like 'STUB-%';"
    status
    ;;
  reset)
    psql_db "delete from catalog.products where id like 'STUB-%';"
    "$0" loadgen 5
    "$0" limit 32 16
    status
    ;;
  *) sed -n '2,/^$/p' "$0"; exit 1 ;;
esac
