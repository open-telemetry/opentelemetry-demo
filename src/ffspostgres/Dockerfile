# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM postgres:16.1-alpine

COPY ./src/ffspostgres/init-scripts/ /docker-entrypoint-initdb.d/

EXPOSE 5432
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["postgres"]
