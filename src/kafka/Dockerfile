# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM registry.ddbuild.io/images/mirror/confluentinc/cp-kafka:7.5.2

USER root
ARG version=2.0.0
ADD https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/download/v$version/opentelemetry-javaagent.jar /tmp/opentelemetry-javaagent.jar
RUN chmod go+r /tmp/opentelemetry-javaagent.jar

USER appuser

ENV KAFKA_LISTENERS=PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093
ENV KAFKA_BROKER_ID=1
ENV KAFKA_ZOOKEEPER_CONNECT='opentelemetry-demo-zookeeper:2181'
ENV KAFKA_LISTENER_SECURITY_PROTOCOL_MAP=CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT
ENV KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://:9092,PLAINTEXT_INTERNAL://:29092
ENV KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1
ENV KAFKA_TRANSACTION_STATE_LOG_MIN_ISR=1
ENV KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR=1
ENV KAFKA_AUTO_CREATE_TOPICS_ENABLE=true

ENV KAFKA_JMX_OPTS="-Dcom.sun.management.jmxremote -Dcom.sun.management.jmxremote.authenticate=false -Dcom.sun.management.jmxremote.ssl=false -Djava.rmi.server.hostname=opentelemetry-demo-kafka -Dcom.sun.management.jmxremote.port=1099 -Dcom.sun.management.jmxremote.rmi.port=1099"
ENV JMX_PORT=1099