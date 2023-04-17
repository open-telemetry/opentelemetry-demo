# dataservice

This service will init ad data and storage into mysql. The adservice-v2 will call dataservice to get ad data.

## setup

1. mysql
```shell
docker run -it --rm \
    -e MYSQL_ROOT_PASSWORD=otel \
    -e MYSQL_DATABASE=otel \
    -p 3306:3306 \
    docker.m.daocloud.io/mysql:8.0.31
```

2. dataservice
```shell
java -jar dataservice-0.0.1-SNAPSHOT.jar
```