# build context will only work from ../../docker-compose.yml
FROM rust:1.61-alpine as builder
RUN apk update
RUN apk add --no-cache ca-certificates git protoc cmake clang clang-dev make gcc g++ libc-dev linux-headers
WORKDIR /app/

# build app
COPY ./src/shippingservice/ /app/
COPY ./pb/ /app/proto/
RUN cargo build -r --features="dockerproto"

# -----------------------------------------------------------------------------

FROM alpine
RUN apk add --no-cache ca-certificates

WORKDIR /app
COPY --from=includer --chmod=0755 /grpc_health_probe /include/
COPY --from=builder /app/target/release/shippingservice /shippingservice

HEALTHCHECK CMD /include/grpc_health_probe -addr :${SHIPPING_SERVICE_PORT}
EXPOSE ${SHIPPING_SERVICE_PORT}
ENTRYPOINT ["/shippingservice"]
