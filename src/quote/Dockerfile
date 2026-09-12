# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM ghcr.io/mlocati/php-extension-installer:2.11.12@sha256:b6d3fa381b9ba5cf051117c1c601d6a523b590e534bf3d56eb4fbe352949c138 AS installer

FROM docker.io/library/composer:2.10.3@sha256:d8f6343d3fae98107426bc49163ccad46ef85aabd4a27d80a74401fab4aba332 AS vendor

WORKDIR /tmp/

COPY ./src/quote/composer.json composer.json

RUN composer install \
    --ignore-platform-reqs \
    --no-interaction \
    --no-plugins \
    --no-scripts \
    --no-dev \
    --prefer-dist

FROM docker.io/library/php:8.5.10-cli-alpine3.24@sha256:aa66ee4275e0472bafcd18e35142499fcbda6ac90e641e751418e052e6a0d812

COPY --from=installer /usr/bin/install-php-extensions /usr/local/bin/

RUN install-php-extensions opcache pcntl protobuf opentelemetry

WORKDIR /var/www

USER www-data

COPY --from=vendor /tmp/vendor/ vendor/

COPY ./src/quote/app/ app/
COPY ./src/quote/public/ public/
COPY ./src/quote/src/ src/

ARG QUOTE_PORT=8090
EXPOSE ${QUOTE_PORT}

CMD ["php", "public/index.php"]
