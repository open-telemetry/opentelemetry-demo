# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY src/mcp/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY src/mcp/src src
COPY src/agent/src/agents/tools.py src/mcp_server
COPY src/mcp/run.py .

EXPOSE ${MCP_PORT}

CMD ["python", "run.py"]
