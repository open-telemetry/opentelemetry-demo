# NOTE: The overall helm chart 

https://github.com/openinsight-proj/openinsight-helm-charts


# adservice-springcloud

This repo re-implements opentelemetry-demo-webstore's adservice with nacos registry and sentinel.

## integrate list

- [x] nacos
- [x] sentinel

## curl

```shell
grpcurl -plaintext -d '{"context_keys": ["binoculars","telescopes"]}' localhost:8080 hipstershop.AdService/GetAds
```

## metrics

adservice-springcloud will emit two metrics:

| Name                                   | Description              | Unit | Type      |
| -------------------------------------- | ------------------------ | ---- | --------- |
| adservice_grpc_call_total              | record grpc call totals  | N/A  | Counter   |
| adservice_grpc_duration_seconds_bucket | record grpc call latency | ms   | histogram |

## mock latency

the `hipstershop.AdService/GetAds` API will do a matrix calculation internally, you can use  `-Dspring.matrixRow=200`
to specific the matrix size

## mock error

the `hipstershop.AdService/GetAds` API will return error randomly(50%), you can use `-Dspring.randomError=false`
to disable this feature.


## Integrate to Nacos and Sentinel

* Please notes the bootstrap.yml file:

  ```
  adservice/src/main/resources/bootstrap.yml
  ```

* Make sure your Dockerfile has: `JAVA_OPTS` env:

  ```
  $JAVA_OPTS -jar /bin/xxx.jar
  ```

* Update the `-D` parms as you want, example like below, for more details please see in `bootstrap.yml`:

  ```
  # Export Sentinel Prometheus metrics
  -javaagent:./jmx_prometheus_javaagent-0.17.0.jar=12345:./prometheus-jmx-config.yaml \
  # Enable Nacos registry integration
  -Dspring.cloud.nacos.discovery.enabled=true \
  # Nacos registry server address
  -Dspring.cloud.nacos.discovery.server-addr=nacos-test.skoala-test:8848 \
  # Nacos registry server username
  -Dspring.cloud.nacos.discovery.username=nacos \
  # Nacos registry server password
  -Dspring.cloud.nacos.discovery.password=nacos \
  # Enable Nacos configuration integration
  -Dspring.cloud.nacos.config.enabled=true \
  # Nacos configuration server address
  -Dspring.cloud.nacos.config.server-addr=nacos-test.skoala-test:8848 \
  # Nacos configuration server username
  -Dspring.cloud.nacos.config.username=nacos \
  # Nacos configuration server password
  -Dspring.cloud.nacos.config.password=nacos \
  # Nacos service name
  -Dspring.application.name=adservice-springcloud \
  # For DCE 5.0 need below Kubernetes metadata
  -Dspring.cloud.nacos.discovery.metadata.k8s_cluster_name=xxx \
  -Dspring.cloud.nacos.discovery.metadata.k8s_namespace_name=xxx \
  -Dspring.cloud.nacos.discovery.metadata.k8s_workload_type=deployment \
  -Dspring.cloud.nacos.discovery.metadata.k8s_workload_name=adservice-springcloud \
  -Dspring.cloud.nacos.discovery.metadata.k8s_service_name=adservice-springcloud \
  -Dspring.cloud.nacos.discovery.metadata.k8s_pod_name=${HOSTNAME} \
  # Enable Sentinel integration
  -Dspring.cloud.sentinel.enabled=true \
  # Sentinel dashboard address
  -Dspring.cloud.sentinel.transport.dashboard=nacos-test-sentinel.skoala-test:8080
  ```

