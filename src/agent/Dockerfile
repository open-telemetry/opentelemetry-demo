# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928

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
