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

run_tracetest() {
  test_file=$1

  TRACETEST_DEV=true tracetest -c ./cli-config.yml test run -d $test_file -w
  return $?
}

check_if_tracetest_is_installed

echo "Starting tests..."

EXIT_STATUS=0

# run tech based tests
echo ""
echo "Running tech based tests..."
run_tracetest ./tech-based-tests/ad-service/get.yaml || EXIT_STATUS=$?
run_tracetest ./tech-based-tests/cart-service/all.yaml || EXIT_STATUS=$?
run_tracetest ./tech-based-tests/currency-service/convert.yaml || EXIT_STATUS=$?
run_tracetest ./tech-based-tests/currency-service/supported.yaml || EXIT_STATUS=$?
run_tracetest ./tech-based-tests/checkout-service/place-order.yaml || EXIT_STATUS=$?
run_tracetest ./tech-based-tests/email-service/confirmation.yaml || EXIT_STATUS=$?
run_tracetest ./tech-based-tests/payment-service/valid-credit-card.yaml || EXIT_STATUS=$?
run_tracetest ./tech-based-tests/payment-service/invalid-credit-card.yaml || EXIT_STATUS=$?
run_tracetest ./tech-based-tests/payment-service/amex-credit-card-not-allowed.yaml || EXIT_STATUS=$?
run_tracetest ./tech-based-tests/payment-service/expired-credit-card.yaml || EXIT_STATUS=$?
run_tracetest ./tech-based-tests/product-catalog-service/list.yaml || EXIT_STATUS=$?
run_tracetest ./tech-based-tests/product-catalog-service/get.yaml || EXIT_STATUS=$?
run_tracetest ./tech-based-tests/product-catalog-service/search.yaml || EXIT_STATUS=$?
run_tracetest ./tech-based-tests/recommendation-service/list.yaml || EXIT_STATUS=$?
run_tracetest ./tech-based-tests/shipping-service/quote.yaml || EXIT_STATUS=$?
run_tracetest ./tech-based-tests/shipping-service/empty-quote.yaml || EXIT_STATUS=$?
run_tracetest ./tech-based-tests/shipping-service/order.yaml || EXIT_STATUS=$?

# run business tests
echo ""
echo "Running business based tests..."
run_tracetest ./business-tests/user-purchase.yaml || EXIT_STATUS=$?

echo ""
echo "Tests done! Exit code: $EXIT_STATUS"

exit $EXIT_STATUS