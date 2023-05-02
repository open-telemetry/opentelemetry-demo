# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM ruby:3.2.2-alpine as base

FROM base as builder
WORKDIR /tmp
COPY Gemfile .
RUN apk update && \
    apk add make gcc musl-dev && \
    bundle install


FROM base as release
WORKDIR /email_server
COPY . .
COPY --from=builder /usr/local/bundle/ /usr/local/bundle/
EXPOSE ${EMAIL_SERVICE_PORT}
ENTRYPOINT ["bundle", "exec", "ruby", "email_server.rb"]
