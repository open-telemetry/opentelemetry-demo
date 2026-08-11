# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM docker.io/library/python:3.15.0rc1-slim-bookworm@sha256:6e3246a49a188d62360dcd248aafbc1834db4d86eff6b28f40ba13269c1bcc57

WORKDIR /build

COPY ./src/recommendation/genproto/requirements.txt requirements.txt

RUN python -m pip install --no-cache-dir --require-hashes -r requirements.txt
