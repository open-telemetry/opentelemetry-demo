# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM alpine

WORKDIR /app

RUN apk --update add bash jq curl
#RUN curl -L https://raw.githubusercontent.com/kubeshop/tracetest/main/install-cli.sh | bash

RUN curl -L https://github.com/kubeshop/tracetest/releases/download/v0.11.10-rc.2/tracetest_0.11.10-rc.2_linux_i386.tar.gz --output /tmp/cli.tar.gz
RUN tar -xf /tmp/cli.tar.gz -C /tmp
RUN mv /tmp/tracetest /usr/local/bin/tracetest
RUN rm -f /tmp/cli.tar.gz

COPY ./test/tracetesting ./test/tracetesting
COPY ./pb ./pb

WORKDIR /app/test/tracetesting

CMD ["/bin/sh", "/app/test/tracetesting/run.bash"]
