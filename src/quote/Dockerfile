# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM ghcr.io/mlocati/php-extension-installer:2.11.1@sha256:bd9ea77afcbc8e55e58d55ca9a39153925367e972827d2f648c949fd0e44aaca AS installer

FROM docker.io/library/composer:2.10.1@sha256:26cb27d1f66af16f8f4d83d522f79ce9d1ea6d80e6bc2d3926af01b000f102ba AS vendor

WORKDIR /tmp/

COPY ./src/quote/composer.json composer.json

RUN composer install \
    --ignore-platform-reqs \
    --no-interaction \
    --no-plugins \
    --no-scripts \
    --no-dev \
    --prefer-dist

FROM docker.io/library/php:8.5.7-cli-alpine3.22@sha256:e385c7a3f12be94b03181f102682df429120f244109107399ba8a45b596ed677

COPY --from=installer /usr/bin/install-php-extensions /usr/local/bin/

RUN install-php-extensions opcache pcntl protobuf opentelemetry

WORKDIR /var/www

USER www-data

COPY --from=vendor /tmp/vendor/ vendor/

COPY ./src/quote/app/ app/
COPY ./src/quote/public/ public/
COPY ./src/quote/src/ src/

EXPOSE ${QUOTE_PORT}

CMD ["php", "public/index.php"]
