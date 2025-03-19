# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM golang:1.22.0-alpine AS builder

WORKDIR /usr/src/app/

RUN apk add build-base protobuf-dev protoc

COPY ./src/productcatalogservice/ ./
RUN GOTOOLCHAIN=local go build -o /go/bin/productcatalogservice/

# -----------------------------------------------------------------------------

FROM alpine AS release

WORKDIR /usr/src/app/

COPY ./src/productcatalogservice/products/ ./products/
COPY --from=builder /go/bin/productcatalogservice/ ./

EXPOSE ${PRODUCT_SERVICE_PORT}
ENTRYPOINT [ "./productcatalogservice" ]
