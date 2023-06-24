# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM alpine

WORKDIR /app

RUN apk --update add bash jq curl
RUN curl -L https://raw.githubusercontent.com/kubeshop/tracetest/main/install-cli.sh | bash

COPY ./test/tracetesting ./test/tracetesting
COPY ./pb ./pb

WORKDIR /app/test/tracetesting

CMD ["/bin/sh", "/app/test/tracetesting/run.bash"]
