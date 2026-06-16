# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM docker.io/library/python:3.15.0b2-alpine3.23@sha256:8d3de8aae4a0549621b4053ca36a849d89300f7f114d5f5a89a037c783743c62 AS build-venv

RUN apk update && \
    apk add gcc g++ linux-headers

COPY ./src/product-reviews/requirements.txt requirements.txt

RUN python -m venv venv && \
    venv/bin/pip install --no-cache-dir --require-hashes -r requirements.txt

RUN venv/bin/opentelemetry-bootstrap -a install

FROM docker.io/library/python:3.15.0b2-alpine3.23@sha256:8d3de8aae4a0549621b4053ca36a849d89300f7f114d5f5a89a037c783743c62

COPY --from=build-venv /venv/ /venv/

WORKDIR /app

COPY ./src/product-reviews/demo_pb2_grpc.py demo_pb2_grpc.py
COPY ./src/product-reviews/demo_pb2.py demo_pb2.py
COPY ./src/product-reviews/product_reviews_server.py product_reviews_server.py
COPY ./src/product-reviews/database.py database.py
COPY ./src/product-reviews/metrics.py metrics.py


EXPOSE ${PRODUCT_REVIEWS_PORT}
ENTRYPOINT [ "/venv/bin/opentelemetry-instrument", "/venv/bin/python", "product_reviews_server.py" ]
