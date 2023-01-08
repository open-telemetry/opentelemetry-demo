FROM eclipse-temurin:17 AS builder

WORKDIR /usr/src/app/

COPY ./src/frauddetectionservice/ ./
COPY ./pb/ ./src/main/proto/
RUN chmod +x ./gradlew
RUN ./gradlew shadowJar

# -----------------------------------------------------------------------------

FROM eclipse-temurin:17

ARG version=1.16.0

RUN addgroup --system mygroup
RUN adduser --system --shell /sbin/nologin --ingroup mygroup myuser

WORKDIR /usr/src/app/

RUN chown myuser:mygroup /usr/src/app/


COPY --from=builder --chown=myuser:mygroup /usr/src/app/build/libs/frauddetectionservice-1.0-all.jar ./
ADD https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/download/v$version/opentelemetry-javaagent.jar /app/opentelemetry-javaagent.jar
RUN chmod 644 /app/opentelemetry-javaagent.jar
RUN chown myuser:mygroup /app/opentelemetry-javaagent.jar
ENV JAVA_TOOL_OPTIONS=-javaagent:/app/opentelemetry-javaagent.jar

USER myuser
ENTRYPOINT [ "java", "-jar", "frauddetectionservice-1.0-all.jar" ]
