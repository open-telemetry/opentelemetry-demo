# Product Reviews Service

This service returns product reviews for a specific product, along with an AI-generated 
summary of the product reviews. 

## Local Build

To build the protos, run from the root directory:

```sh
make docker-generate-protobuf
```

## Docker Build

From the root directory, run:

```sh
docker compose build product-reviews
```
