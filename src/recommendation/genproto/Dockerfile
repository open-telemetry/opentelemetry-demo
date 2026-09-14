# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM docker.io/library/python:3.14.7-slim-bookworm@sha256:9ab8d9c8514b44f90cf0029dd42fdd7e9e211e639c8b995304cc04568dee900f

WORKDIR /build

COPY ./src/recommendation/genproto/requirements.txt requirements.txt

RUN python -m pip install --no-cache-dir --require-hashes -r requirements.txt
