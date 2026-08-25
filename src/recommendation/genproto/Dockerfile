# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM docker.io/library/python:3.14.7-slim-bookworm@sha256:23c59390fc717bf09f9336908199a0ae75d9c4264bf296123f94ad772fea3b52

WORKDIR /build

COPY ./src/recommendation/genproto/requirements.txt requirements.txt

RUN python -m pip install --no-cache-dir --require-hashes -r requirements.txt
