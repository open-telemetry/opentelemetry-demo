#/bin/bash

set -e

run_tracetest() {
  test_file=$1

  tracetest -c ./cli-config.yml test run -d $test_file -w
  return $?
}

run_tracetest_with_env() {
  test_file=$1
  env_file=$2

  tracetest -c ./cli-config.yml test run -d $test_file --environment $env_file -w
  return $?
}

echo "Starting tests..."

EXIT_STATUS=0

# run tech based tests
echo ""
echo "Running tech based tests..."
run_tracetest ./tech-based-tests/ad-get.yaml || EXIT_STATUS=$?
run_tracetest ./tech-based-tests/currency-convert.yaml || EXIT_STATUS=$?
run_tracetest ./tech-based-tests/currency-supported.yaml || EXIT_STATUS=$?

# run business tests
echo ""
echo "Running business based tests..."
run_tracetest_with_env ./business-tests/user-purchase.yaml ./business-tests/environment-vars.env || EXIT_STATUS=$?

echo ""
echo "Tests done! Exit code: $EXIT_STATUS"

exit $EXIT_STATUS