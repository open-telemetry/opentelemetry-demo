# Service Testing

The OpenTelemetry Demo uses traced-based testing to validate the
functionality of the services and the traces they generate.

The trace-based tests will each service and validate the traces they
generate and stored in Jaeger, to a known working trace for the same operation.

## Testing services with Trace-based tests

To run the entire test suite of trace-based tests, run the command:

```sh
make run-tracetesting
#or
docker compose run traceBasedTests
```

To run tests for specific services, pass the name of the service as a
parameter (using the folder names located [here](./tracetesting/)):

```sh
make run-tracetesting SERVICES_TO_TEST="service-1 service-2 ..."
#or
docker compose run traceBasedTests "service-1 service-2 ..."
```

For instance, if you need to run the tests for `ad` and `payment`, you can run
them with:

```sh
make run-tracetesting SERVICES_TO_TEST="ad payment"
```
