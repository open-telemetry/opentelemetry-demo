FROM eclipse-temurin:17-jdk AS builder

WORKDIR /app/

COPY ./src/dataservice/  ./
RUN ./mvnw --batch-mode clean package -DskipTests

# -----------------------------------------------------------------------------

FROM docker.m.daocloud.io/library/openjdk:11.0.15-jre

WORKDIR /app/
ARG version=1.23.0

COPY --from=builder /app/target/dataservice-0.0.1-SNAPSHOT.jar ./

ADD https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/download/v$version/opentelemetry-javaagent.jar /usr/src/app/opentelemetry-javaagent.jar

RUN chmod 644 /usr/src/app/opentelemetry-javaagent.jar

ENV OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
    OTEL_RESOURCE_ATTRIBUTES=service.name=dataservice \
    JAVA_TOOL_OPTIONS=-javaagent:/usr/src/app/opentelemetry-javaagent.jar \
    JAVA_OPTS=' -Dotel.jmx.target.system=tomcat -Dspring.cloud.nacos.config.enabled=false'

EXPOSE 8080 8999

ENTRYPOINT java $JAVA_OPTS -jar dataservice-0.0.1-SNAPSHOT.jar
