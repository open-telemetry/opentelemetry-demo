# Ad Service

The Ad service provides advertisement based on context keys. If no context keys
are provided then it returns random ads.

## Building locally

The Ad service uses gradlew to compile/install/distribute. Gradle wrapper is
already part of the source code. To build Ad Service, run:

```sh
./gradlew installDist
```

It will create executable script src/adservice/build/install/hipstershop/bin/AdService

### Upgrading gradle version

If you need to upgrade the version of gradle then run

```sh
./gradlew wrapper --gradle-version <new-version>
```

## Building docker image

From `src/adservice/`, run:

```sh
docker build ./
```

## Run the client sample locally

### Build a image for Ad Service

```sh
cd  /${project}/opentelemetry-demo-webstore/src/adservice
docker build -t  adservice:v1  . 
```

### Run a instance for Ad Service by Docker

```sh
docker run -d -p 9555:9555 adservice:v1 
```

### Enter into the docker instance and start a client demo

You can use `docker exec -it ${CONTAINER_ID} /bin/sh`

```sh
docker exec -it 3d6a8db7322a /bin/sh
sh /app/build/install/hipstershop/bin/AdServiceClient
```

### Check if Ad Service is successful to start by logs of this client

```sh
2022-06-03 17:57:11 - hipstershop.AdServiceClient - Get Ads with context camera ... trace_id= span_id= trace_flags= 
2022-06-03 17:57:12 - hipstershop.AdServiceClient - Ads: Hairdryer for sale. 50% off. trace_id= span_id= trace_flags= 
2022-06-03 17:57:12 - hipstershop.AdServiceClient - Ads: Bamboo glass jar for sale. 10% off. trace_id= span_id= trace_flags= 
```
