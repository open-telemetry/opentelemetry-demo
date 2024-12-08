# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM python:3.12-slim-bookworm AS base

FROM base AS builder
RUN apt-get -qq update \
    && apt-get install -y --no-install-recommends g++ \
    && rm -rf /var/lib/apt/lists/*

COPY ./src/loadgenerator/requirements.txt .
RUN pip install --prefix="/reqs" -r requirements.txt
ARG DD_GIT_REPOSITORY_URL
ARG DD_GIT_COMMIT_SHA
ENV DD_GIT_REPOSITORY_URL=${DD_GIT_REPOSITORY_URL} 
ENV DD_GIT_COMMIT_SHA=${DD_GIT_COMMIT_SHA}
FROM base
WORKDIR /usr/src/app/
COPY --from=builder /reqs /usr/local
COPY ./src/loadgenerator/locustfile.py .
COPY ./src/loadgenerator/people.json .
ENV LOCUST_PLAYWRIGHT=1
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers
RUN playwright install --with-deps chromium
ENTRYPOINT ["locust", "--skip-log-setup"]
