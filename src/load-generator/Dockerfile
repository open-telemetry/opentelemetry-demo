# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM python:3.12-slim-bookworm AS build-venv

ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

COPY ./src/load-generator/requirements.txt requirements.txt

RUN python -m venv venv
RUN venv/bin/pip install --no-cache-dir -r requirements.txt

RUN venv/bin/playwright install --with-deps chromium

FROM gcr.io/distroless/python3-debian12:nonroot

ENV PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers

COPY --from=build-venv /venv/ /venv/
COPY --from=build-venv /opt/playwright/ /opt/pw-browsers/

WORKDIR /app

COPY ./src/load-generator/locustfile.py locustfile.py
COPY ./src/load-generator/people.json people.json

ENTRYPOINT ["/venv/bin/locust", "--skip-log-setup"]
