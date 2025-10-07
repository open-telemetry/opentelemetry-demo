# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM mysql:9.4.0

COPY ./src/mysql/init-scripts/ /docker-entrypoint-initdb.d/

EXPOSE ${MYSQL_PORT}
