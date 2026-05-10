# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM python:3.12-alpine

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /tests
WORKDIR /tests

ENTRYPOINT ["pytest"]
CMD ["--tb=short", "-v"]
