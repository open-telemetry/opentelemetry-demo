# Welcome to Aspecto

To run this demo and send traces to Aspecto:

1. clone this repo
  ```sh
  git clone https://github.com/aspecto-io/opentelemetry-demo.git
  ```

2. [Sign Up](https://app.aspecto.io/) to create a free account in aspecto

3. Copy your [aspecto token](https://app.aspecto.io/86092cc0/integration/tokens) and paste it in [`./src/otelcollector/otelcol-config-extras.yml`](./src/otelcollector/otelcol-config-extras.yml) instead of `<your_aspecto_token>`

```
exporters:
  otlp/aspecto:
    endpoint: otelcol.aspecto.io:4317
    headers:
      Authorization: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

service:
  pipelines:
    traces:
      exporters: [logging, otlp, otlp/aspecto]
```

4. Run the demo

- [Docker](./docs/docker_deployment.md)
- [Kubernetes](./docs/kubernetes_deployment.md)

5. Browse to [Trace Search](https://app.aspecto.io/86092cc0/search?relative=15m&sort=endTimestamp&order=1&page=0) to search and view the traces from the demo run
