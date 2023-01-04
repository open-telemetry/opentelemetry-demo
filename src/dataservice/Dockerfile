FROM eclipse-temurin:17-jdk AS builder

WORKDIR /app/

COPY ./src/dataservice/  ./
RUN ./mvnw --batch-mode clean package -DskipTests

# -----------------------------------------------------------------------------

FROM docker.m.daocloud.io/library/openjdk:11.0.15-jre

WORKDIR /app/

COPY --from=builder /app/target/dataservice-0.0.1-SNAPSHOT.jar ./

RUN set -ex; \
    curl -L -O https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/download/v1.19.2/opentelemetry-javaagent.jar;

ENV OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
    OTEL_RESOURCE_ATTRIBUTES=service.name=dataservice \
    JAVA_TOOL_OPTIONS=-javaagent:opentelemetry-javaagent.jar \
    JAVA_OPTS='-Dspring.cloud.nacos.config.enabled=false'

EXPOSE 8082 8999 8888

ENTRYPOINT java $JAVA_OPTS -jar dataservice-0.0.1-SNAPSHOT.jar
