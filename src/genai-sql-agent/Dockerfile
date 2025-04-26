# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# Adapted from https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
FROM python:3.13-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Change the working directory to the `app` directory
WORKDIR /app

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=./src/genai-sql-agent/uv.lock,target=uv.lock \
    --mount=type=bind,source=./src/genai-sql-agent/pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project
ENV PATH="/app/.venv/bin/:$PATH"

# Copy the project into the image
COPY ./src/genai-sql-agent/ /app

# Sync the project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

CMD [ "opentelemetry-instrument", "streamlit", "run", "--client.toolbarMode=developer", "--server.baseUrlPath=genai-sql-agent", "agent.py" ]
