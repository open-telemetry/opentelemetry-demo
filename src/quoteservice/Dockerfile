# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM composer:2.4 AS build

WORKDIR /tmp/
COPY ./src/quoteservice/composer.json .

RUN composer install \
    --ignore-platform-reqs \
    --no-interaction \
    --no-plugins \
    --no-scripts \
    --no-dev \
    --prefer-dist

FROM php:8.2-cli

ADD https://github.com/mlocati/docker-php-extension-installer/releases/latest/download/install-php-extensions /usr/local/bin/
RUN chmod +x /usr/local/bin/install-php-extensions \
  && install-php-extensions \
    opcache \
    pcntl \
    protobuf \
    opentelemetry-1.0.0beta3

WORKDIR /var/www
COPY --from=build /tmp/vendor/ ./vendor/
COPY ./src/quoteservice/ /var/www

CMD php public/index.php

USER www-data
EXPOSE ${QUOTE_SERVICE_PORT}
