# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM python:3.14-slim@sha256:a7fb1e634c4a578f9e0bd6327f11a3cde11b7a9395f48e24360c0988bcc5c2bc

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY src/mcp/requirements.txt .

RUN pip install --no-cache-dir --require-hashes -r requirements.txt

COPY src/mcp/src src
COPY src/shared/tools.py src/mcp_server
COPY src/mcp/run.py .

EXPOSE ${MCP_PORT}

CMD ["python", "run.py"]
