# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM golang:1.22-alpine AS builder

WORKDIR /usr/src/app/

RUN --mount=type=cache,target=/go/pkg/mod/ \
    --mount=type=bind,source=./src/checkoutservice/go.sum,target=go.sum \
    --mount=type=bind,source=./src/checkoutservice/go.mod,target=go.mod \
    go mod download

RUN --mount=type=cache,target=/go/pkg/mod/ \
    --mount=type=cache,target=/root/.cache/go-build \
    --mount=type=bind,rw,source=./src/checkoutservice,target=. \
    go build -ldflags "-s -w" -o /go/bin/checkoutservice/ ./

FROM alpine

WORKDIR /usr/src/app/
ARG DD_GIT_REPOSITORY_URL
ARG DD_GIT_COMMIT_SHA
ENV DD_GIT_REPOSITORY_URL=${DD_GIT_REPOSITORY_URL} 
ENV DD_GIT_COMMIT_SHA=${DD_GIT_COMMIT_SHA}

COPY --from=builder /go/bin/checkoutservice/ ./

EXPOSE ${CHECKOUT_SERVICE_PORT}
ENTRYPOINT [ "./checkoutservice" ]
