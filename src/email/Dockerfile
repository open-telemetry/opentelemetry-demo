# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM ruby:3.2.2-slim AS base

FROM base AS builder

WORKDIR /tmp

COPY ./src/email/Gemfile ./src/email/Gemfile.lock ./

#RUN apk update && apk add make gcc musl-dev gcompat && bundle install
RUN apt-get update && apt-get install build-essential -y && bundle install
FROM base AS release

WORKDIR /email_server

COPY ./src/email/ .

RUN chmod 666 ./Gemfile.lock

COPY --from=builder /usr/local/bundle/ /usr/local/bundle/


EXPOSE ${EMAIL_PORT}
ENTRYPOINT ["bundle", "exec", "ruby", "email_server.rb"]
