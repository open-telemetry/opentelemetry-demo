# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM ghcr.io/mlocati/php-extension-installer:2.12.0@sha256:1afade3e29cfc97362cf5885e5ac333bf2faab1146cb28ebbb59b17e68f87e88 AS installer

FROM docker.io/library/composer:2.10.3@sha256:9715c7f69044da2a212a5fbde29ee7da24e364d426560ae6367b060236f847d7 AS vendor

WORKDIR /tmp/

COPY ./src/quote/composer.json composer.json

RUN composer install \
    --ignore-platform-reqs \
    --no-interaction \
    --no-plugins \
    --no-scripts \
    --no-dev \
    --prefer-dist

FROM docker.io/library/php:8.5.10-cli-alpine3.24@sha256:4992c6fda82eadfb3b22dca3929188dc5831e9f44a3d42b3c8d36a460b4d5a80

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
