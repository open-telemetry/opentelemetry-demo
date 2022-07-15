# OpenTelemetry Demo with Instana Backend

This repo is a fork of the original [OpenTelemetry Demo](https://github.com/open-telemetry/opentelemetry-demo) with added integration to Instana host-agent OTLP endpoint and application infrastructure monitoring configuration.

## Build and run the demo webstore app

Follow the main [README](README.md). This is basically:
```sh
docker compose up
```

### In case you are behing an HTTP proxy ...
Configure the Docker client according to https://docs.docker.com/network/proxy/ by adding the following snippet to `~/.docker/config.json`
```json
{
 "proxies":
 {
   "default":
   {
     "httpProxy": "http://192.168.31.253:3128",
     "httpsProxy": "http://192.168.31.253:3128",
     "noProxy": "192.168.0.0/16,.tec.cz.ibm.com,127.0.0.0/8"
   }
 }
}
```

Create a new gradle properties file `src/adservice/gradle.properties` with your proxy settings:
```
systemProp.https.proxyHost=192.168.31.253
systemProp.https.proxyPort=3128
```

Build the Webstore app with `http_proxy` and `https_proxy` environment variables passed to `docker-compose`:
```sh
docker compose build \ 
    --build-arg 'https_proxy=http://192.168.31.253:3128' \
    --build-arg 'http_proxy=http://192.168.31.253:3128' \
    --build-arg 'no_proxy=localhost,127.0.0.1,127.0.1.1,.tec.cz.ibm.com,192.168.0.0/16' \
    --no-cache
```

## Build and run Instana host agent

Create an environment file for `docker-compose` with your Instana endpoint connection configuration and keys. Use the template:
```sh
cd instana-agent
cp instana-agent.env.template .env
```

Edit the OTEL Collector configuration file [`src/otelcollector/otelcol-config.yml`](src/otelcollector/otelcol-config.yml) and replace the Instana endpoint with your host IP or DNS-resolvable hostname. Use the actual host interface IP; don't use `localhost` or `127.0.0.1` as the collector must be able to reach the IP from inside a container.

Launch the agent (inside the `instana-agent` directory):
```sh
docker compose up -d
```

