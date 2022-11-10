FROM composer:2.4.1 AS build

WORKDIR /tmp/
COPY ./src/quoteservice/composer.json .

RUN composer install \
    --ignore-platform-reqs \
    --no-interaction \
    --no-plugins \
    --no-scripts \
    --no-dev \
    --prefer-dist

FROM php:8.1-cli

# install GRPC (required for the OTel exporter)
# RUN apt-get -y update && apt install -y --no-install-recommends zlib1g-dev && \
#    pecl install grpc protobuf-3.21.5 && \
#    docker-php-ext-enable grpc protobuf

WORKDIR /var/www
COPY --from=build /tmp/vendor/ /var/www/vendor/
COPY ./src/quoteservice/ /var/www

EXPOSE ${QUOTE_SERVICE_PORT}

ENTRYPOINT php -S 0.0.0.0:${QUOTE_SERVICE_PORT} -t public
