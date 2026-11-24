# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM python:3.15-slim@sha256:1c670c3568107e243bfd05457ad9ca0b11c35a855c985af73e4452db9a714e70

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY src/chatbot/requirements.txt .

RUN pip install --no-cache-dir --require-hashes -r requirements.txt

COPY src/chatbot/src src
COPY src/chatbot/run.py .

ARG CHATBOT_PORT=7860
EXPOSE ${CHATBOT_PORT}

CMD ["python", "run.py"]
