# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY src/agent/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY src/agent/src src
COPY src/agent/run.py .

EXPOSE ${MCP_PORT}
EXPOSE ${AGENT_PORT}
EXPOSE ${CHATBOT_PORT}

CMD ["python", "run.py"]
