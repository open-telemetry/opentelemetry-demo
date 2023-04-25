FROM eclipse-temurin:17-jdk AS builder

WORKDIR /usr/src/app/

COPY ./src/businessmetricservice/gradlew* ./src/businessmetricservice/settings.gradle* ./src/businessmetricservice/build.gradle .
COPY ./src/businessmetricservice/gradle ./gradle

RUN ./gradlew
RUN ./gradlew downloadRepos

COPY ./src/businessmetricservice/ ./
COPY ./pb/ ./proto
RUN ./gradlew installDist -PprotoSourceDir=./proto

# -----------------------------------------------------------------------------

FROM eclipse-temurin:17-jre

WORKDIR /usr/src/app/

COPY --from=builder /usr/src/app/ ./

#NOTE: This service is intended to be instrumented through the OTel Operator in
#k8s. If you are running through compose, uncomment this next section.
#ARG version=1.24.0
#ADD https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/download/v$version/opentelemetry-javaagent.jar /usr/src/app/opentelemetry-javaagent.jar
#RUN chmod 644 /usr/src/app/opentelemetry-javaagent.jar
#ENV JAVA_TOOL_OPTIONS=-javaagent:/usr/src/app/opentelemetry-javaagent.jar

ENV KAFKA_BOOTSTRAP_SERVERS=localhost:9092
ENTRYPOINT [ "./build/install/opentelemetry-demo-business-metric-service/bin/BusinessMetricService" ]
