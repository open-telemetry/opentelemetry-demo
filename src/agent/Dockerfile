# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM python:3.14-slim@sha256:ce40764625a4ff50df3548277632e7f96c4e77fe75fa848aae9885476e7df5a4

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
