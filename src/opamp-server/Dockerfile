# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM golang:1.27.4-alpine@sha256:70bd7ddea8b6cbe5d6943cde279d6b67feb10cc924fb9100d1d8757c1575b280 AS builder

ARG OPAMP_GO_VERSION

RUN apk add --no-cache git

WORKDIR /src/opamp-go
RUN git init && \
    git remote add origin https://github.com/open-telemetry/opamp-go.git && \
    git fetch --depth 1 origin refs/tags/v${OPAMP_GO_VERSION} && \
    git checkout FETCH_HEAD

RUN sed -i 's|href="/"|href="/opamp/"|g' internal/examples/html/html/agent.html && \
    awk ' \
      /Additional Configuration:/ { skip = "td"; next } \
      /<form action="\/rotate_client_cert"/ { skip = "form"; next } \
      /<h3>OpAMP Connection Settings<\/h3>/ { skip = "form"; next } \
      /<h3>Custom Messages<\/h3>/ { exit } \
      skip == "td" && /<\/td>/ { skip = ""; next } \
      skip == "form" && /<\/form>/ { skip = ""; next } \
      skip == "" { print } \
    ' internal/examples/html/html/agent.html > /tmp/agent.html && \
    mv /tmp/agent.html internal/examples/html/html/agent.html && \
    sed -i 's|"/agent?instanceid=|"/opamp/agent?instanceid=|g' \
      internal/examples/server/uisrv/ui.go

WORKDIR /src/opamp-go/internal/examples
RUN go build -trimpath -ldflags="-s -w" -o /opamp-server ./server

FROM alpine:3.24@sha256:f59abe656b692d901e184be3445e084786602108599d2a51d229c0f5a48c71bf

RUN apk add --no-cache ca-certificates

COPY --from=builder /opamp-server /opamp-server

EXPOSE 4320
EXPOSE 4321

ENTRYPOINT ["/opamp-server"]
