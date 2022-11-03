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

FROM php:8.1-apache

# install GRPC (required for the OTel exporter)
RUN apt-get -y update && apt install -y --no-install-recommends zlib1g-dev && \
   pear config-set http_proxy ${http_proxy} && \
   MAKEFLAGS="-j $(nproc)" pecl install grpc protobuf-3.21.5 && \
   strip -s $(find /usr -name grpc.so) && \
   docker-php-ext-enable grpc protobuf

RUN docker-php-ext-install opcache

WORKDIR /var/www
COPY --from=build /tmp/vendor/ ./vendor/
COPY ./src/quoteservice/ /var/www

ENV APACHE_DOCUMENT_ROOT /var/www/public
RUN sed -ri -e 's|/var/www/html|${APACHE_DOCUMENT_ROOT}|g' /etc/apache2/sites-available/*.conf
RUN a2enmod rewrite
RUN echo "ServerName quoteservice" >> /etc/apache2/apache2.conf

EXPOSE ${QUOTE_SERVICE_PORT}

ENTRYPOINT sed -i "s/80/${QUOTE_SERVICE_PORT}/g" /etc/apache2/sites-available/000-default.conf /etc/apache2/ports.conf \
&& apache2-foreground
