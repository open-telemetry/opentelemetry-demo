#!/usr/bin/env bash

# add vx to debug
set -euo pipefail
SCRIPTDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

log() { echo "$1" >&2; }

# NB: we *want* to split on spaces, so disable this check here
# shellcheck disable=SC2086
run() { 
    log "$2"
    docker run -d --rm --network=$networkName \
    -e OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=$otelCollector \
    -e OTEL_RESOURCE_ATTRIBUTES=service.name=$containername,service.version=$TAG \
    $1 --name $2 $2:$TAG >&2 || true
}

check_network() {
    echo "Checking if $networkName network exists, if not, it will be created."
    for existing_network in $(docker network ls --format '{{.Name}}')
    do
        if [ "$existing_network" = "$networkName" ]
        then
            return;
        fi
    done

    docker network create "$networkName"
}

TAG="${TAG:?TAG env variable must be specified}"
networkName=online-boutique
otelCollectorName=otelcollector
otelCollector="http://$otelCollectorName:4317"

check_network

while IFS= read -d $'\0' -r dir; do
    # build image
    svcname="$(basename "${dir}")"
    builddir="${dir}"
    #PR 516 moved cartservice build artifacts one level down to src
    if [ "$svcname" == "cartservice" ] 
    then
        builddir="${dir}/src"
    fi
    image="$svcname:$TAG"
    (
        cd "${builddir}"
        log "Building: ${image}"
        docker build -t "${image}" .
    )
done < <(find "${SCRIPTDIR}/../src" -mindepth 1 -maxdepth 1 -type d -print0)

log "Successfully built all images."

log "Deploying Otel-Collector and Jaeger:"

docker run -d --rm --network="$networkName" --name jaeger \
  -e COLLECTOR_ZIPKIN_HOST_PORT=:9411 \
  -p 5775:5775/udp \
  -p 6831:6831/udp \
  -p 6832:6832/udp \
  -p 5778:5778 \
  -p 16686:16686 \
  -p 14250:14250 \
  -p 14268:14268 \
  -p 14269:14269 \
  -p 9411:9411 \
  jaegertracing/all-in-one:1.31 || true

containername="$otelCollectorName"
docker run -d --rm --network="$networkName" \
     --name "$otelCollectorName" \
     "$otelCollectorName:$TAG" >&2 || true


log "Deploying Online Boutique:"

containername=redis-cart
docker run -d --rm --network="$networkName" \
    -p 6379 -v redis-data:/data \
    --name "$containername" redis:alpine || true

containername=adservice
run "-p 9555 -e PORT=9555 \
     " "$containername"

containername=cartservice
run "-p 7070 -e REDIS_ADDR=redis-cart:6379 \
     -e OTEL_EXPORTER_OTLP_ENDPOINT=$otelCollector \
     " "$containername"

containername=checkoutservice
run "-p 5050 -e PORT=5050 \
     -e PRODUCT_CATALOG_SERVICE_ADDR=productcatalogservice:3550 \
     -e SHIPPING_SERVICE_ADDR=shippingservice:50051 \
     -e PAYMENT_SERVICE_ADDR=paymentservice:50051 \
     -e EMAIL_SERVICE_ADDR=emailservice:8080 \
     -e CURRENCY_SERVICE_ADDR=currencyservice:7000 \
     -e CART_SERVICE_ADDR=cartservice:7070" "$containername"

containername=currencyservice
run "-p 7000 -e PORT=7000 \
     " "$containername"

containername=emailservice
run "-p 8080 -e PORT=8080 \
     -e OTEL_PYTHON_LOG_CORRELATION=true \
     " "$containername"

containername=frontend
run "-p 8080:8080 -e PORT=8080 \
     -e PRODUCT_CATALOG_SERVICE_ADDR=productcatalogservice:3550 \
     -e SHIPPING_SERVICE_ADDR=shippingservice:50051 \
     -e CURRENCY_SERVICE_ADDR=currencyservice:7000 \
     -e CART_SERVICE_ADDR=cartservice:7070 \
     -e RECOMMENDATION_SERVICE_ADDR=recommendationservice:8080 \
     -e CHECKOUT_SERVICE_ADDR=checkoutservice:5050 \
     -e AD_SERVICE_ADDR=adservice:9555" "$containername"

containername=paymentservice
run "-p 50051 -e PORT=50051 \
     " "$containername"

containername=productcatalogservice
run "-p 3550 -e PORT=3550 \
     " "$containername"

containername=recommendationservice
run "-p 8080 -e PORT=8080 \
     -e OTEL_PYTHON_LOG_CORRELATION=true \
     -e PRODUCT_CATALOG_SERVICE_ADDR=productcatalogservice:3550 \
     " "$containername"

containername=shippingservice
run "-p 50051 -e PORT=50051 \
     " "$containername"

containername=loadgenerator
run "-e FRONTEND_ADDR=frontend:8080 \
     -e USERS=10" "$containername"
