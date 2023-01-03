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

FROM php:8.2-apache

ADD https://github.com/mlocati/docker-php-extension-installer/releases/latest/download/install-php-extensions /usr/local/bin/
RUN chmod +x /usr/local/bin/install-php-extensions \
  && install-php-extensions \
    opcache \
    protobuf \
    open-telemetry/opentelemetry-php-instrumentation@1.0.0beta1

WORKDIR /var/www
COPY --from=build /tmp/vendor/ ./vendor/
COPY ./src/quoteservice/ /var/www

ENV APACHE_DOCUMENT_ROOT /var/www/public
RUN sed -ri -e 's|/var/www/html|${APACHE_DOCUMENT_ROOT}|g' /etc/apache2/sites-available/*.conf \
    && a2enmod rewrite \
    && echo "ServerName quoteservice" >> /etc/apache2/apache2.conf \
    && sed -i "s/80/\$\{QUOTE_SERVICE_PORT\}/g" /etc/apache2/sites-available/000-default.conf /etc/apache2/ports.conf

USER www-data
EXPOSE ${QUOTE_SERVICE_PORT}
