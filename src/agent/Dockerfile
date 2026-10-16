# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM python:3.14-slim@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170

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

ARG AGENT_PORT=8010
EXPOSE ${AGENT_PORT}

CMD ["python", "run.py"]
