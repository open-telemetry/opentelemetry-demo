# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM registry.ddbuild.io/images/mirror/golang:1.22-alpine AS builder
WORKDIR /usr/src/app/

COPY ./src/accountingservice/ ./
RUN go build -o /go/bin/accountingservice/

# -----------------------------------------------------------------------------

FROM alpine

WORKDIR /usr/src/app/

COPY --from=builder /go/bin/accountingservice/ ./

ENTRYPOINT [ "./accountingservice" ]
