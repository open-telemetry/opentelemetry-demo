# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM python:3.14-slim@sha256:d3400aa122fa42cf0af0dbe8ec3091b047eac5c8f7e3539f7135e86d855dc015

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY src/agent/requirements.txt .

RUN pip install --no-cache-dir --require-hashes -r requirements.txt

COPY src/agent/src src
COPY src/shared/tools.py src/agents
COPY src/agent/run.py .

EXPOSE ${AGENT_PORT}

CMD ["python", "run.py"]
