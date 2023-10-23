# Quote Service

The Quote Service calculates the shipping costs,
based on the number of items to be shipped.

It is a PHP based service, using a combination of automatic and manual instrumentation.

## Docker Build

To build the quote service, run the following from root directory
of opentelemetry-demo

```sh
docker compose build quoteservice
```

## Run the service

Execute the below command to run the service.

```sh
docker compose up quoteservice
```

In order to get traffic into the service you have to deploy
the whole opentelemetry-demo.

Please follow the root README to do so.

## Development

To build and run the quote service locally:

```sh
docker build src/quoteservice --target base -t quoteservice
cd src/quoteservice
docker run --rm -it -v $(pwd):/var/www -e QUOTE_SERVICE_PORT=8999 -p "8999:8999" quoteservice
```

Then, send some curl requests:

```sh
curl --location 'http://localhost:8999/getquote' \
--header 'Content-Type: application/json' \
--data '{"numberOfItems":3}'
```
