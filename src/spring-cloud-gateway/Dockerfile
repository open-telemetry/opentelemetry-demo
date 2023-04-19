FROM eclipse-temurin:17-jdk AS builder

WORKDIR /app/

COPY ./src/spring-cloud-gateway/  ./
RUN ./mvnw --batch-mode clean package -DskipTests

# -----------------------------------------------------------------------------

FROM docker.m.daocloud.io/library/openjdk:11.0.15-jre

WORKDIR /app/

COPY --from=builder /app/target/spring-cloud-gateway-0.0.1-SNAPSHOT.jar ./

EXPOSE 18080

ENTRYPOINT java $JAVA_OPTS -jar spring-cloud-gateway-0.0.1-SNAPSHOT.jar
