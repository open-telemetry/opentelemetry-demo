# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM nginxinc/nginx-unprivileged:1.29.0-alpine3.22-otel

# CVE-2026-111497: brotli-libs (pulled in by libcurl, libfreetype) fixed in 1.1.1-r0
USER root
RUN apk upgrade --no-cache brotli-libs

USER 101

COPY src/image-provider/static/ /static/
COPY src/image-provider/nginx.conf.template /nginx.conf.template

EXPOSE ${IMAGE_PROVIDER_PORT}

STOPSIGNAL SIGQUIT

# Start nginx
CMD ["/bin/sh" , "-c" , "envsubst '$OTEL_COLLECTOR_HOST $IMAGE_PROVIDER_PORT $OTEL_COLLECTOR_PORT_GRPC $OTEL_SERVICE_NAME' < /nginx.conf.template > /etc/nginx/nginx.conf && cat  /etc/nginx/nginx.conf && exec nginx -g 'daemon off;'"]
