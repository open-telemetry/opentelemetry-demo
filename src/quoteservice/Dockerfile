# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM php:8.3-cli AS base

ADD https://github.com/mlocati/docker-php-extension-installer/releases/latest/download/install-php-extensions /usr/local/bin/
RUN chmod +x /usr/local/bin/install-php-extensions \
  && install-php-extensions \
  opcache \
  pcntl \
  protobuf \
  opentelemetry

WORKDIR /var/www
CMD ["php", "public/index.php"]
USER www-data
EXPOSE ${QUOTE_SERVICE_PORT}

FROM composer:2.7 AS vendor

WORKDIR /tmp/
COPY ./src/quoteservice/composer.json .
ARG DD_GIT_REPOSITORY_URL
ARG DD_GIT_COMMIT_SHA
ENV DD_GIT_REPOSITORY_URL=${DD_GIT_REPOSITORY_URL} 
ENV DD_GIT_COMMIT_SHA=${DD_GIT_COMMIT_SHA}
RUN composer install \
  --ignore-platform-reqs \
  --no-interaction \
  --no-plugins \
  --no-scripts \
  --no-dev \
  --prefer-dist

FROM base AS final
COPY --from=vendor /tmp/vendor/ ./vendor/
COPY ./src/quoteservice/ /var/www
