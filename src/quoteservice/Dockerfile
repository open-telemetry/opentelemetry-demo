FROM composer:2.4.1 AS build

WORKDIR /tmp/
COPY ./src/quoteservice/composer.json .

RUN composer install \
    --ignore-platform-reqs \
    --no-interaction \
    --no-plugins \
    --no-scripts \
    --prefer-dist

FROM php:8.1-apache-buster

# install GRPC (required for the OTel exporter)
RUN apt-get -y update && apt install -y --no-install-recommends zlib1g-dev && \
    pecl install grpc && \
    docker-php-ext-enable grpc

WORKDIR /var/www
COPY --from=build /tmp/vendor/ /var/www/vendor/
COPY ./src/quoteservice/ /var/www

EXPOSE 8090

ENTRYPOINT ["php", "-S", "0.0.0.0:8090", "-t", "public"]
