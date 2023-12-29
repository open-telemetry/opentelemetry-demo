# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM golang:1.21.4-alpine AS builder

WORKDIR /usr/src/app/

RUN apk add build-base protobuf-dev protoc

COPY ./src/productcatalogservice/ ./
RUN go build -o /go/bin/productcatalogservice/

# -----------------------------------------------------------------------------

FROM alpine AS release

WORKDIR /usr/src/app/

COPY ./src/productcatalogservice/products.json ./
COPY --from=builder /go/bin/productcatalogservice/ ./

EXPOSE ${PRODUCT_SERVICE_PORT}
ENTRYPOINT [ "./productcatalogservice" ]
