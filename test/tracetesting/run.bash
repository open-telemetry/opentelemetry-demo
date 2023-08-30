# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0
#/bin/bash

# This script set up how to run Tracetest and which test files 
# be executed

set -e

check_if_tracetest_is_installed() {
  if ! command -v tracetest &> /dev/null
  then
      echo "tracetest CLI could not be found"
      exit -1
  fi
}

create_env_file() {
  cat << EOF > tracetesting-env.yaml
type: Environment
spec:
  id: tracetesting-env
  name: tracetesting-env
  values:
    - key: AD_SERVICE_ADDR
      value: $AD_SERVICE_ADDR
    - key: CART_SERVICE_ADDR
      value: $CART_SERVICE_ADDR
    - key: CHECKOUT_SERVICE_ADDR
      value: $CHECKOUT_SERVICE_ADDR
    - key: CURRENCY_SERVICE_ADDR
      value: $CURRENCY_SERVICE_ADDR
    - key: EMAIL_SERVICE_ADDR
      value: $EMAIL_SERVICE_ADDR
    - key: FRONTEND_ADDR
      value: $FRONTEND_ADDR
    - key: PAYMENT_SERVICE_ADDR
      value: $PAYMENT_SERVICE_ADDR
    - key: PRODUCT_CATALOG_SERVICE_ADDR
      value: $PRODUCT_CATALOG_SERVICE_ADDR
    - key: RECOMMENDATION_SERVICE_ADDR
      value: $RECOMMENDATION_SERVICE_ADDR
    - key: SHIPPING_SERVICE_ADDR
      value: $SHIPPING_SERVICE_ADDR
EOF
}

run_tracetest() {
  service_name=$1
  transaction_file=./$service_name/all.yaml

  tracetest --config ./cli-config.yml run transaction --file $transaction_file --environment ./tracetesting-env.yaml
  return $?
}

ALL_SERVICES=("ad-service" "cart-service" "currency-service" "checkout-service" "frontend-service" "email-service" "payment-service" "product-catalog-service" "recommendation-service" "shipping-service")
CHOSEN_SERVICES=()

while [[ $# -gt 0 ]]; do
  CHOSEN_SERVICES+=("$1")
  shift
done

if [ ${#CHOSEN_SERVICES[@]} -eq 0 ]; then
  for service in "${ALL_SERVICES[@]}"; do
    CHOSEN_SERVICES+=("$service")  
  done
fi

check_if_tracetest_is_installed
create_env_file

echo "Starting tests..."

EXIT_STATUS=0

echo ""
echo "Running trace-based tests..."
echo ""

for service in "${CHOSEN_SERVICES[@]}"; do
  run_tracetest $service || EXIT_STATUS=$?
done

echo ""
echo "Tests done! Exit code: $EXIT_STATUS"

exit $EXIT_STATUS