# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# Build stage: compile llama-cpp-python and download model
FROM docker.io/library/python:3.12-slim-bookworm AS build

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential g++ curl && \
    rm -rf /var/lib/apt/lists/*

COPY ./src/llm/requirements.txt requirements.txt

ENV CMAKE_ARGS="-DGGML_NATIVE=OFF" CMAKE_BUILD_PARALLEL_LEVEL=2
RUN python -m venv /venv && \
    /venv/bin/pip install --no-cache-dir -r requirements.txt

# Download SmolLM2-135M-Instruct Q4_K_M GGUF (~105MB)
RUN mkdir -p /models && \
    curl -L -o /models/SmolLM2-135M-Instruct-Q4_K_M.gguf \
    "https://huggingface.co/lmstudio-community/SmolLM2-135M-Instruct-GGUF/resolve/main/SmolLM2-135M-Instruct-Q4_K_M.gguf"

# Runtime stage
FROM docker.io/library/python:3.12-slim-bookworm

RUN apt-get update && \
    apt-get install -y --no-install-recommends libgomp1 && \
    rm -rf /var/lib/apt/lists/*

COPY --from=build /venv/ /venv/
COPY --from=build /models/ /app/models/

WORKDIR /app

COPY ./src/llm/app.py app.py

EXPOSE ${LLM_PORT}
ENTRYPOINT [ "/venv/bin/python", "app.py" ]
