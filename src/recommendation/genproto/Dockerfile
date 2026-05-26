# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM python:3.14-slim-bookworm

WORKDIR /build

COPY ./src/recommendation/genproto/requirements.lock.txt requirements.lock.txt

RUN python -m pip install --no-cache-dir --require-hashes -r requirements.lock.txt
