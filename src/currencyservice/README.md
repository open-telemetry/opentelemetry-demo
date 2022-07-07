# Currency Service

The Currency Service does the conversion from one currency to another. It is a C++ based service.

## Building docker image

To build the currency service, run the following from root directory of opentelemetry-demo-webstore

> docker-compose build currencyservice

## Run the service

Execute the below command to run the service.

> docker-compose up currencyservice

## Run the client

currencyclient is a sample client which sends some request to currency service. To run the client, execute the below command.

> docker exec -it <container-name> currencyclient 7000

'7000' is port where currencyservice listens to.
