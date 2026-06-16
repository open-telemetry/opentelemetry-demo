# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM docker.io/library/python:3.15.0b2-slim-bookworm@sha256:5e946dab0224498220fff2f032782e0a87c8ec7d2cbf94d7dad884e9ffd0a274

WORKDIR /build

COPY ./src/product-reviews/genproto/requirements.txt requirements.txt

RUN python -m pip install --no-cache-dir --require-hashes -r requirements.txt
