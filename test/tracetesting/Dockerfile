# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM docker.io/library/alpine:3.24.0@sha256:a2d49ea686c2adfe3c992e47dc3b5e7fa6e6b5055609400dc2acaeb241c829f4

WORKDIR /app

# The build-images workflow action does not set a build-arg so we need to specify a default value here
ARG TRACETEST_IMAGE_VERSION

RUN apk --update add bash jq curl
RUN curl -L https://raw.githubusercontent.com/kubeshop/tracetest/main/install-cli.sh | bash -s -- $TRACETEST_IMAGE_VERSION

WORKDIR /app/test/tracetesting

ENTRYPOINT ["/bin/bash", "/app/test/tracetesting/run.bash"]
