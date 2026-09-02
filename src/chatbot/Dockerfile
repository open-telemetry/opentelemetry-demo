# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM python:3.14-slim@sha256:656d12e70054d5fda18a045e2494c96701e9792dd1445f95b3d038df954f57e9

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY src/chatbot/requirements.txt .

RUN pip install --no-cache-dir --require-hashes -r requirements.txt

COPY src/chatbot/src src
COPY src/chatbot/run.py .

EXPOSE ${CHATBOT_PORT}

CMD ["python", "run.py"]
