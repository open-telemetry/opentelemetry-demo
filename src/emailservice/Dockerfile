# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM ruby:3.2.2-slim AS base

FROM base AS builder

WORKDIR /tmp

COPY ./src/emailservice/Gemfile ./src/emailservice/Gemfile.lock ./

#RUN apk update && apk add make gcc musl-dev gcompat && bundle install
RUN apt-get update && apt-get install build-essential -y && bundle install
FROM base AS release

WORKDIR /email_server

COPY ./src/emailservice/ .

RUN chmod 666 ./Gemfile.lock

COPY --from=builder /usr/local/bundle/ /usr/local/bundle/

ARG DD_GIT_REPOSITORY_URL
ARG DD_GIT_COMMIT_SHA
ENV DD_GIT_REPOSITORY_URL=${DD_GIT_REPOSITORY_URL} 
ENV DD_GIT_COMMIT_SHA=${DD_GIT_COMMIT_SHA}

EXPOSE ${EMAIL_SERVICE_PORT}
ENTRYPOINT ["bundle", "exec", "ruby", "email_server.rb"]
