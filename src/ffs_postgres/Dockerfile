FROM postgres:16.1
WORKDIR /app
COPY ./src/ffs_postgres/init.sh /docker-entrypoint-initdb.d
COPY ./src/ffs_postgres/dump.sql ./dump.sql
