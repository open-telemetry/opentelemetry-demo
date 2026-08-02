# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src
WORKDIR /app

COPY src/demo-llm/requirements.in .

RUN pip install --no-cache-dir \
      --extra-index-url https://download.pytorch.org/whl/cpu \
      -r requirements.in

COPY src/demo-llm/src src
COPY src/demo-llm/artifacts artifacts
COPY src/demo-llm/run.py .

EXPOSE ${DEMO_LLM_PORT}

CMD ["python", "run.py"]
