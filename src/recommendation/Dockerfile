# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM python:3.12-slim-bookworm AS base

#
# Fetch requirements
#
FROM base AS builder
RUN apt-get -qq update \
    && apt-get install -y --no-install-recommends g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/app/
COPY ./src/recommendation/requirements.txt ./

RUN pip install --upgrade pip
RUN pip install --prefix="/reqs" -r requirements.txt

#
# Runtime
#
FROM base AS runtime
WORKDIR /usr/src/app/
COPY --from=builder /reqs /usr/local
COPY ./src/recommendation/ ./

RUN opentelemetry-bootstrap -a install

EXPOSE ${RECOMMENDATION_PORT}
ENTRYPOINT [ "opentelemetry-instrument", "python", "recommendation_server.py" ]
