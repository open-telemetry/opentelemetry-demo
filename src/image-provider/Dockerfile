# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM docker.io/nginxinc/nginx-unprivileged:1.31.7-alpine3.24-otel@sha256:d3c3765065f95ae1b98396275d445b687a1a0611561505afa584335359209213

USER 101

COPY src/image-provider/static/ /static/
COPY src/image-provider/nginx.conf.template /nginx.conf.template

ARG IMAGE_PROVIDER_PORT=8081
EXPOSE ${IMAGE_PROVIDER_PORT}

STOPSIGNAL SIGQUIT

# Start nginx
CMD ["/bin/sh" , "-c" , "envsubst '$OTEL_COLLECTOR_HOST $IMAGE_PROVIDER_PORT $OTEL_COLLECTOR_PORT_GRPC $OTEL_SERVICE_NAME' < /nginx.conf.template > /etc/nginx/nginx.conf && cat  /etc/nginx/nginx.conf && exec nginx -g 'daemon off;'"]
