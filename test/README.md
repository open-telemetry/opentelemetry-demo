# Service Testing

There are two ways to test the service APIs in the OpenTelemetry Demo:

1. Using black box-testing, calling gRPC services
and validating their direct response
2. Using Trace-based tests, calling both HTTP and
gRPC services and validating their direct response as well as
the distributed traces they generate

## Testing gRPC services as black boxes

To run the entire test suite as a black box, run the command:

```sh
docker compose run integrationTests
```

If you want to run tests for a specific service, run:

1. Start the services you want to test with `docker compose up --build <service>`
2. Run `npm install`
3. Run `npm test` or `npx ava --match='<pattern>'` to match test names

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

For instance, if you need to run the tests for `ad-service` and
`payment-service`, you can run them with:

```sh
make run-tracetesting SERVICES_TO_TEST="ad-service payment-service"
```
