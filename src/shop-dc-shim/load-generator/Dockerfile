# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM python:3.11-alpine

WORKDIR /app

# Install dependencies
COPY ./load-generator/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy load generator
COPY ./load-generator/shop_load_generator.py shop_load_generator.py

# Create non-root user
RUN addgroup -g 1001 -S loadgen && \
    adduser -S loadgen -u 1001 -G loadgen

USER loadgen

ENV PYTHONUNBUFFERED=1

# Default to continuous load generation
ENTRYPOINT ["python", "shop_load_generator.py"]
CMD ["--mode", "continuous", "--tpm", "5", "--duration", "0"]
