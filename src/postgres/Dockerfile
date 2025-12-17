# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM postgres:18.1

COPY ./src/postgres/init.sql /docker-entrypoint-initdb.d/init.sql

EXPOSE ${POSTGRES_PORT}
