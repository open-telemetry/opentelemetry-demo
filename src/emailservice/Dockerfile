# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM ruby:3.2.2-slim as base

FROM base as builder

WORKDIR /tmp

COPY Gemfile Gemfile.lock .

#RUN apk update && apk add make gcc musl-dev gcompat && bundle install
RUN apt-get update && apt-get install build-essential -y && bundle install

FROM base as release

WORKDIR /email_server

COPY . .

RUN apt-get update && apt-get install -y python3 python3-pip python3-venv && \
    python3 -m venv ./venv && \
    ./venv/bin/pip install --no-cache-dir -r requirements.txt && \
    chmod 666 ./Gemfile.lock && \
    chmod +x entrypoint.sh

COPY --from=builder /usr/local/bundle/ /usr/local/bundle/

EXPOSE ${EMAIL_SERVICE_PORT}

ENTRYPOINT ["./entrypoint.sh"]
