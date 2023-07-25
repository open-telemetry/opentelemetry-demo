# Service Testing

There are two ways to test the service APIs on this demo:

1. Using black box testing, calling gRPC services
and validating its direct response
2. Using Trace-based tests, calling services
and validating its direct response and traces

## Testing gRPC services as black boxes

To run the entire test suite as a blackbox you need just to run the command:

```sh
docker compose run integrationTests
```

Now if you want the tests for a specific service:

1. Start the services you want to test with `docker compose up --build <service>`
2. Run `npm install`
3. Run `npm test` or `npx ava --match='<pattern>'` to match test names

## Testing services with Trace-based tests

To run the entire test suite of trace-based tests you can run the command:

```sh
make run-tracetesting
#or
docker compose run traceBasedTests
```

To run tests for specific services, you can pass the name of the service as a
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
