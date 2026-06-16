# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM docker.io/library/python:3.15.0b2-alpine3.22@sha256:8374b202f092c233441f36b3018fd839c5c42d58b0a8ea479860f9ff2326d8cf AS build-venv

RUN apk update && \
    apk add gcc g++ linux-headers

COPY ./src/llm/requirements.txt requirements.txt

RUN python -m venv venv && \
    venv/bin/pip install --no-cache-dir --require-hashes -r requirements.txt

FROM docker.io/library/python:3.15.0b2-alpine3.22@sha256:8374b202f092c233441f36b3018fd839c5c42d58b0a8ea479860f9ff2326d8cf

COPY --from=build-venv /venv/ /venv/

WORKDIR /app

COPY ./src/llm/app.py app.py
COPY ./src/llm/product-review-summaries/product-review-summaries.json product-review-summaries.json
COPY ./src/llm/product-review-summaries/inaccurate-product-review-summaries.json inaccurate-product-review-summaries.json

EXPOSE ${LLM_PORT}
ENTRYPOINT [ "/venv/bin/python", "app.py" ]
