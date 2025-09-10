FROM eclipse-temurin:21-jdk AS builder

WORKDIR /usr/src/app

COPY *.gradle gradlew* .
COPY ./gradle ./gradle
COPY ./pb ./proto
RUN chmod +x ./gradlew

RUN ./gradlew downloadRepos             ## Downloading the dependencies

COPY . .

RUN ./gradlew installDist -PprotoSourceDir=./proto

FROM eclipse-temurin:21-jre AS release

WORKDIR /usr/src/app

COPY --from=builder /usr/src/app/build/install/opentelemetry-demo-ad ./opentelemetry-demo-ad

ENV AD_PORT=8080
ENV FEATURE_FLAG_GRPC_SERVICE_ADDR=featureflagservice:50053

ENTRYPOINT ["./opentelemetry-demo-ad/bin/Ad"]
