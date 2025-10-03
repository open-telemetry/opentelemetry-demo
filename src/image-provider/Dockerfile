# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM nginxinc/nginx-unprivileged:1.29.0-alpine3.22-otel

USER 101

COPY src/image-provider/static/ /static/
COPY src/image-provider/nginx.conf.template /nginx.conf.template

# Set default value for OTEL_* config if not provided by Docker Compose or K8s
ENV OTEL_SERVICE_NAME="image-provider"
ENV OTEL_COLLECTOR_HOST=localhost
ENV OTEL_COLLECTOR_PORT_GRPC=4317

EXPOSE ${IMAGE_PROVIDER_PORT}

STOPSIGNAL SIGQUIT

# Start nginx
CMD ["/bin/sh" , "-c" , "envsubst '$OTEL_COLLECTOR_HOST $IMAGE_PROVIDER_PORT $OTEL_COLLECTOR_PORT_GRPC $OTEL_SERVICE_NAME' < /nginx.conf.template > /etc/nginx/nginx.conf && cat  /etc/nginx/nginx.conf && exec nginx -g 'daemon off;'"]
