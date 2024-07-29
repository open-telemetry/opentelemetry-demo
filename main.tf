terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 2.13.0"
    }
  }
}

variable "project_path" {
  type = string
  default = "C:\\Users\\Pasca\\Documents\\Uni\\Master\\3. Semester\\Enpro\\opentelemetry-demo"
  description = "Path to the project"
}

variable "seperator" {
  type = string
  default = "\\"
  description = "Path seperator"
}

provider "docker" {
  host = "npipe:////.//pipe//docker_engine"
}


# Network Ressource
resource "docker_network" "open-telemetry-network" {
  name   = "opentelemetry-demo"
  driver = "bridge"
}

# accounting service container
resource "docker_container" "accountingservice-container" {
  name       = "accounting-service"
  image      = "ghcr.io/open-telemetry/demo:latest-accountingservice"
  depends_on = [docker_container.otelcol, docker_container.kafka]
  network_mode = "bridge"
  networks_advanced {
    name = docker_network.open-telemetry-network.name
  }
  hostname = "accountingservice"
  memory     = 20
  restart    = "unless-stopped"
  env = [
    "KAFKA_SERVICE_ADDR=kafka:9092",
    "OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317",
    "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=Cumulative",
    "OTEL_RESOURCE_ATTRIBUTES=docker.cli.cobra.command_path=docker%20compose",
    "OTEL_SERVICE_NAME = accountingservice"
  ]


}

#ad service container
resource "docker_container" "adservice-container" {
  name       = "ad-service"
  image      = "ghcr.io/open-telemetry/demo:latest-adservice"
  depends_on = [docker_container.otelcol, docker_container.flagd]
  network_mode = "bridge"
  networks_advanced {
    name = docker_network.open-telemetry-network.name
  }
  hostname = "adservice"
  memory     = 300
  restart    = "unless-stopped"
  ports {
    internal = 9555
  }
  env = [
    "AD_SERVICE_PORT=9555",
    "FLAGD_HOST=flagd",
    "FLAGD_PORT=8013",
    "OTEL_EXPORTER_OTLP_ENDPOINT=http://otelcol:4318",
    "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=Cumulative",
    "OTEL_RESOURCE_ATTRIBUTES=docker.cli.cobra.command_path=docker%20compose",
    "OTEL_LOGS_EXPORTER=otlp",
    "OTEL_SERVICE_NAME=adservice"
  ]
}

#cart service container

resource "docker_container" "cartservice-container" {
  name       = "cart-service"
  image      = "ghcr.io/open-telemetry/demo:latest-cartservice"
  depends_on = [docker_container.valkey-cart, docker_container.otelcol, docker_container.flagd]
  network_mode = "bridge"
  networks_advanced {
    name = docker_network.open-telemetry-network.name
  }
  hostname = "cartservice"
  memory     = 160
  restart    = "unless-stopped"
  ports {
    internal = 7070
  }
  env = [
    "CART_SERVICE_PORT=7070",
    "FLAGD_HOST=flagd",
    "FLAGD_PORT=8013",
    "REDIS_ADDR=redis-cart:6379",
    "VALKEY_ADDR=valkey-cart:6379",
    "OTEL_EXPORTER_OTLP_ENDPOINT=http://otelcol:4318",
    "OTEL_RESOURCE_ATTRIBUTES=docker.cli.cobra.command_path=docker%20compose",
    "OTEL_SERVICE_NAME=cartservice",
    "ASPNETCORE_URLS=http://*:7070"
  ]

}

# checkout service container

resource "docker_container" "checkoutservice-container" {
  name  = "checkout-service"
  image = "ghcr.io/open-telemetry/demo:latest-checkoutservice"
  depends_on = [docker_container.cartservice-container,
    docker_container.currencyservice-container,
    docker_container.emailservice-container,
    docker_container.paymentservice,
    docker_container.productcatalogservice,
    docker_container.shippingservice,
    docker_container.otelcol,
  docker_container.flagd]
  network_mode = "bridge"
  networks_advanced {
    name = docker_network.open-telemetry-network.name
  }
  hostname = "checkoutservice"
  memory  = 20
  restart = "unless-stopped"
  ports {
    internal = 5050
  }
  env = [
    "FLAGD_HOST =flagd",
    "FLAGD_PORT =8013",
    "CHECKOUT_SERVICE_PORT=5050",
    "CART_SERVICE_ADDR=cart-service:7070",
    "CURRENCY_SERVICE_ADDR=currencyservice:7001",
    "EMAIL_SERVICE_ADDR=http://emailservice:6060",
    "PAYMENT_SERVICE_ADDR=paymentservice:50051",
    "PRODUCT_CATALOG_SERVICE_ADDR=productcatalogservice:3550",
    "SHIPPING_SERVICE_ADDR=shippingservice:50050",
    "KAFKA_SERVICE_ADDR=kafka:9092",
    "OTEL_EXPORTER_OTLP_ENDPOINT=http://otelcol:4318",
    "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=Cumulative",
    "OTEL_RESOURCE_ATTRIBUTES=docker.cli.cobra.command_path=docker%20compose",
    "OTEL_SERVICE_NAME=checkoutservice"

  ]

}

# currency service container

resource "docker_container" "currencyservice-container" {
  name       = "currency-service"
  image      = "ghcr.io/open-telemetry/demo:latest-currencyservice"
  depends_on = [docker_container.otelcol]
  network_mode = "bridge"
  networks_advanced {
    name = docker_network.open-telemetry-network.name
  }
  hostname = "currencyservice"
  memory     = 20
  restart    = "unless-stopped"
  ports {
    internal = 7001
  }
  env = [
    "CURRENCY_SERVICE_PORT=7001",
    "VERSION=1.10.0",
    "OTEL_EXPORTER_OTLP_ENDPOINT=http://otelcol:4317",
    "OTEL_RESOURCE_ATTRIBUTES=docker.cli.cobra.command_path=docker%20compose ,service.name=currencyservice"
  ]

}

# email service container

resource "docker_container" "emailservice-container" {
  name       = "email-service"
  image      = "demo/emailservice-contrib:latest"
  depends_on = [docker_container.otelcol]
  network_mode = "bridge"
  networks_advanced {
    name = docker_network.open-telemetry-network.name
  }
  hostname = "emailservice"
  memory     = 100
  restart    = "unless-stopped"
  ports {
    internal = 6060
  }
  env = [
    "APP_ENV=production",
    "EMAIL_SERVICE_PORT =6060",
    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://otelcol:4318/v1/traces",
    "OTEL_RESOURCE_ATTRIBUTES=docker.cli.cobra.command_path=docker%20compose",
    "OTEL_SERVICE_NAME=emailservice"
  ]

}

# fraud detection service container

resource "docker_container" "frauddetectionservice-container" {
  name       = "frauddetection-service"
  image      = "ghcr.io/open-telemetry/demo:latest-frauddetectionservice"
  depends_on = [docker_container.otelcol, docker_container.kafka]
  network_mode = "bridge"
  networks_advanced {
    name = docker_network.open-telemetry-network.name
  }
  hostname = "frauddetectionservice"
  memory     = 300
  restart    = "unless-stopped"
  env = [
    "FLAGD_HOST=flagd",
    "FLAGD_PORT=8013",
    "KAFKA_SERVICE_ADDR=kafka:9092",
    "OTEL_EXPORTER_OTLP_ENDPOINT=http://otelcol:4318",
    "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=Cumulative",
    "OTEL_INSTRUMENTATION_KAFKA_EXPERIMENTAL_SPAN_ATTRIBUTES=true",
    "OTEL_INSTRUMENTATION_MESSAGING_EXPERIMENTAL_RECEIVE_TELEMETRY_ENABLED=true",
    "OTEL_RESOURCE_ATTRIBUTES=docker.cli.cobra.command_path=docker%20compose",
    "OTEL_SERVICE_NAME=frauddetectionservice"
  ]

}

# frontend container

resource "docker_container" "frontend" {
  name  = "frontend"
  image = "ghcr.io/open-telemetry/demo:latest-frontend"
  depends_on = [docker_container.adservice-container,
    docker_container.cartservice-container,
    docker_container.checkoutservice-container,
    docker_container.currencyservice-container,
    docker_container.productcatalogservice,
    docker_container.quoteservice,
    docker_container.recommendationservice,
    docker_container.shippingservice,
    docker_container.otelcol,
    docker_container.imageprovider,
    docker_container.flagd
  ]
  network_mode = "bridge"
  networks_advanced {
    name = docker_network.open-telemetry-network.name
  }
  memory  = 250
  restart = "unless-stopped"
  ports {
    internal = 8080
  }
  env = [
    "PORT=8080",
    "FRONTEND_ADDR=frontend:8080",
    "AD_SERVICE_ADDR=adservice:9555",
    "CART_SERVICE_ADDR=cartservice:7070",
    "CHECKOUT_SERVICE_ADDR=checkoutservice:5050",
    "CURRENCY_SERVICE_ADDR=currencyservice:7001",
    "PRODUCT_CATALOG_SERVICE_ADDR=productcatalogservice:3550",
    "RECOMMENDATION_SERVICE_ADDR=recommendationservice:9001",
    "SHIPPING_SERVICE_ADDR=shippingservice:50050",
    "OTEL_EXPORTER_OTLP_ENDPOINT = http://otelcol:4317",
    "OTEL_RESOURCE_ATTRIBUTES=docker.cli.cobra.command_path=docker%20compose",
    "ENV_PLATFORM = local",
    "OTEL_SERVICE_NAME=frontend",
    "PUBLIC_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://localhost:8080/otlp-http/v1/traces",
    "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=cumulative",
    "WEB_OTEL_SERVICE_NAME=frontend-web",
    "OTEL_COLLECTOR_HOST=otelcol",
    "FLAGD_HOST = flagd",
    "FLAGD_PORT = 8013"
  ]
}

# frontend proxy (envoy) container

resource "docker_container" "frontendproxy" {
  name  = "frontend-proxy"
  image = "ghcr.io/open-telemetry/demo:latest-frontendproxy"
  depends_on = [docker_container.frontend,
    docker_container.loadgenerator,
    docker_container.jaeger,
  docker_container.grafana]
  network_mode = "bridge"
  networks_advanced {
    name = docker_network.open-telemetry-network.name
  }
  hostname = "frontendproxy"
  memory  = 50
  restart = "unless-stopped"
  ports {
    internal = 1000
    external = 1000
  }
  ports {
    internal = 8080
    external = 8080
  }
  env = [
    "FRONTEND_PORT=8080",
    "FRONTEND_HOST=frontend",
    "LOCUST_WEB_HOST=loadgenerator",
    "LOCUST_WEB_PORT=8089",
    "GRAFANA_SERVICE_PORT=3000",
    "GRAFANA_SERVICE_HOST=grafana",
    "JAEGER_SERVICE_PORT=16686",
    "JAEGER_SERVICE_HOST=jaeger",
    "OTEL_COLLECTOR_HOST=otelcol",
    "IMAGE_PROVIDER_HOST=imageprovider",
    "IMAGE_PROVIDER_PORT=8081",
    "OTEL_COLLECTOR_PORT_GRPC=4317",
    "OTEL_COLLECTOR_PORT_HTTP=4318",
    "OTEL_RESOURCE_ATTRIBUTES=docker.cli.cobra.command_path=docker%20compose",
    "ENVOY_PORT=8080",
    "FLAGD_HOST=flagd",
    "FLAGD_PORT=8013"
  ]

}

# image provider container

resource "docker_container" "imageprovider" {
  name       = "image-provider"
  image      = "ghcr.io/open-telemetry/demo:latest-imageprovider"
  depends_on = [docker_container.otelcol]
  network_mode = "bridge"
  networks_advanced {
    name = docker_network.open-telemetry-network.name
  }
  hostname = "imageprovider"
  memory     = 120
  restart    = "unless-stopped"
  ports {
    internal = 8081
  }
  env = [
    "IMAGE_PROVIDER_PORT=8081",
    "OTEL_COLLECTOR_HOST=otelcol",
    "OTEL_COLLECTOR_PORT_GRPC=4317",
    "OTEL_SERVICE_NAME=imageprovider",
    "OTEL_RESOURCE_ATTRIBUTES=docker.cli.cobra.command_path=docker%20compose"
  ]

}

# load generator container

resource "docker_container" "loadgenerator" {
  name  = "load-generator"
  image = "ghcr.io/open-telemetry/demo:latest-loadgenerator"
  depends_on = [docker_container.frontend,
  docker_container.flagd]
  network_mode = "bridge"
  networks_advanced {
    name = docker_network.open-telemetry-network.name
  }
  hostname = "loadgenerator"
  memory  = 1000
  restart = "unless-stopped"
  ports {
    internal = 8089
  }
  env = [
    "LOCUST_WEB_PORT=8089",
    "LOCUST_USERS=10",
    "LOCUST_HOST=http://frontend-proxy:8080",
    "LOCUST_HEADLESS=false",
    "LOCUST_AUTOSTART=true",
    "LOCUST_BROWSER_TRAFFIC_ENABLED=true",
    "OTEL_EXPORTER_OTLP_ENDPOINT=http://otelcol:4317",
    "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=cumulative",
    "OTEL_RESOURCE_ATTRIBUTES=docker.cli.cobra.command_path=docker%20compose",
    "OTEL_SERVICE_NAME=loadgenerator",
    "PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python",
    "LOCUST_WEB_HOST=0.0.0.0",
    "FLAGD_HOST=flagd",
    "FLAGD_PORT=8013"
  ]

}

# payment service container

resource "docker_container" "paymentservice" {
  name  = "payment-service"
  image = "ghcr.io/open-telemetry/demo:latest-paymentservice"
  depends_on = [docker_container.otelcol,
  docker_container.flagd]
  network_mode = "bridge"
  networks_advanced {
    name = docker_network.open-telemetry-network.name
  }
  hostname = "paymentservice"
  memory  = 120
  restart = "unless-stopped"
  ports {
    internal = 50051
  }
  env = [
    "PAYMENT_SERVICE_PORT=50051",
    "FLAGD_HOST=flagd",
    "FLAGD_PORT=8013",
    "OTEL_EXPORTER_OTLP_ENDPOINT=http://otelcol:4317",
    "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=cumulative",
    "OTEL_RESOURCE_ATTRIBUTES=docker.cli.cobra.command_path=docker%20compose",
    "OTEL_SERVICE_NAME=paymentservice"
  ]

}

# product catalog service container

resource "docker_container" "productcatalogservice" {
  name  = "product-catalog-service"
  image = "ghcr.io/open-telemetry/demo:latest-productcatalogservice"
  depends_on = [docker_container.otelcol,
    docker_container.flagd,
  docker_container.mongodb-catalog]
  network_mode = "bridge"
  networks_advanced {
    name = docker_network.open-telemetry-network.name
  }
  hostname = "productcatalogservice"
  memory  = 20
  restart = "unless-stopped"
  ports {
    internal = 3550
  }
  env = [
    "PRODUCT_CATALOG_SERVICE_PORT=3550",
    "FLAGD_HOST=flagd",
    "FLAGD_PORT=8013",
    "OTEL_EXPORTER_OTLP_ENDPOINT=http://otelcol:4317",
    "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=cumulative",
    "OTEL_RESOURCE_ATTRIBUTES=docker.cli.cobra.command_path=docker%20compose",
    "OTEL_SERVICE_NAME=productcatalogservice",
    "MONGO_USERNAME=mongo",
    "MONGO_PASSWORD=mongo_product_catalog",
    "MONGO_HOSTNAME=mongo",
    "MONGO_PORT=27017"
  ]
}

# quote service container

resource "docker_container" "quoteservice" {
  name       = "quote-service"
  image      = "ghcr.io/open-telemetry/demo:latest-quoteservice"
  depends_on = [docker_container.otelcol]
  network_mode = "bridge"
  networks_advanced {
    name = docker_network.open-telemetry-network.name
  }
  hostname = "quoteservice"
  memory     = 40
  restart    = "unless-stopped"
  ports {
    internal = 8090
  }
  env = [
    "OTEL_EXPORTER_OTLP_ENDPOINT=http://otelcol:4318",
    "OTEL_PHP_AUTOLOAD_ENABLED=true",
    "QUOTE_SERVICE_PORT=8090",
    "OTEL_RESOURCE_ATTRIBUTES=docker.cli.cobra.command_path=docker%20compose",
    "OTEL_SERVICE_NAME=quoteservice",
    "OTEL_PHP_INTERNAL_METRICS_ENABLED=true"
  ]

}

# recommendation service container

resource "docker_container" "recommendationservice" {
  name  = "recommendation-service"
  image = "ghcr.io/open-telemetry/demo:latest-recommendationservice"
  depends_on = [docker_container.productcatalogservice,
    docker_container.otelcol,
    docker_container.flagd
  ]
  network_mode = "bridge"
  networks_advanced {
    name = docker_network.open-telemetry-network.name
  }
  hostname = "recommendationservice"
  memory  = 500
  restart = "unless-stopped"
  ports {
    internal = 9001
  }
  env = [
    "RECOMMENDATION_SERVICE_PORT=9001",
    "PRODUCT_CATALOG_SERVICE_ADDR=productcatalogservice:50051",
    "FLAGD_HOST=flagd",
    "FLAGD_PORT=8013",
    "OTEL_PYTHON_LOG_CORRELATION=true",
    "OTEL_EXPORTER_OTLP_ENDPOINT=http://otelcol:4317",
    "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=cumulative",
    "OTEL_RESOURCE_ATTRIBUTES=docker.cli.cobra.command_path=docker%20compose",
    "OTEL_SERVICE_NAME=recommendationservice",
    "PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python"
  ]

}

# shipping service container

resource "docker_container" "shippingservice" {
  name       = "shipping-service"
  image      = "ghcr.io/open-telemetry/demo:latest-shippingservice"
  depends_on = [docker_container.otelcol]
  network_mode = "bridge"
  networks_advanced {
    name = docker_network.open-telemetry-network.name
  }
  hostname = "shippingservice"
  memory     = 20
  restart    = "unless-stopped"
  ports {
    internal = 50050
  }
  env = [
    "SHIPPING_SERVICE_PORT=50050",
    "QUOTE_SERVICE_ADDR=http://quoteservice:8090",
    "OTEL_EXPORTER_OTLP_ENDPOINT=http://otelcol:4317",
    "OTEL_RESOURCE_ATTRIBUTES=docker.cli.cobra.command_path=docker%20compose",
    "OTEL_SERVICE_NAME=shippingservice"
  ]
}

# dependent services

# flagd feature flagging service container

resource "docker_container" "flagd" {
  name   = "flagd"
  image  = "ghcr.io/open-feature/flagd:v0.10.2"
  memory = 50
  env = [
    "FLAGD_OTEL_COLLECTOR_URI=otelcol:4317",
    "FLAGD_METRICS_EXPORTER=otel",
    "OTEL_RESOURCE_ATTRIBUTES=docker.cli.cobra.command_path=docker%20compose",
    "OTEL_SERVICE_NAME=flagd"
  ]
  network_mode = "bridge"
  networks_advanced {
    name = docker_network.open-telemetry-network.name
  }
  command = [
    "start",
    "--uri",
    "file:./etc/flagd/demo.flagd.json"
  ]
  ports {
    internal = 8013
  }
  volumes {
    host_path      = "${var.project_path}${var.seperator}src${var.seperator}flagd"
    container_path = "/etc/flagd"
  }

}

# kafka container

resource "docker_container" "kafka" {
  name    = "kafka"
  image   = "ghcr.io/open-telemetry/demo:latest-kafka"
  memory  = 600
  network_mode = "bridge"
  networks_advanced {
    name = docker_network.open-telemetry-network.name
  }
  restart = "unless-stopped"
  ports {
    internal = 9092
  }
  env = [
    "KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://kafka:9092",
    "OTEL_EXPORTER_OTLP_ENDPOINT=http://otelcol:4318",
    "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=cumulative",
    "OTEL_RESOURCE_ATTRIBUTES=docker.cli.cobra.command_path=docker%20compose",
    "OTEL_SERVICE_NAME=kafka",
    "KAFKA_HEAP_OPTS=-Xmx400m -Xms400m"
  ]
  healthcheck {
    test         = ["nc", "-z", "kafka 9092"]
    start_period = "10s"
    interval     = "5s"
    timeout      = "10s"
    retries      = 10

  }
}

# valkey service container (used by cart container)

resource "docker_container" "valkey-cart" {
  name    = "valkey-cart"
  image   = "valkey/valkey:7.2-alpine"
  user    = "valkey"
  memory  = 20
  restart = "unless-stopped"
  network_mode = "bridge"
  networks_advanced {
    name = docker_network.open-telemetry-network.name
  }
  ports {
    internal = 6379
  }
}

# mongodb service container (used by product catalog container)

resource "docker_container" "mongodb-catalog" {
  name    = "mongodb-catalog"
  image   = "mongo:8.0.0-rc9"
  memory  = 256
  restart = "unless-stopped"
  network_mode = "bridge"
  networks_advanced {
    name = docker_network.open-telemetry-network.name
  }
  hostname = "mongo"
  ports {
    internal = 27017
    external = 27017
  }
  env = [
    "MONGO_INITDB_ROOT_USERNAME=mongo",
    "MONGO_INITDB_ROOT_PASSWORD=mongo_product_catalog"
  ]
  healthcheck {
    test         = [ "echo", "db.runCommand(\"ping\").ok", "|", "mongosh", "localhost:27017/test", "--quiet"]
    start_period = "10s"
    interval     = "5s"
    timeout      = "10s"
    retries      = 10

  }

}

# telemetry components

# jaeger container

resource "docker_container" "jaeger" {
  name  = "jaeger"
  image = "jaegertracing/all-in-one:1.57"
  command = [
    "--memory.max-traces=5000",
    "--query.base-path=/jaeger/ui",
    "--prometheus.server-url=http://prometheus:9090",
    "--prometheus.query.normalize-calls=true",
    "--prometheus.query.normalize-duration=true"
  ]
  memory  = 400
  restart = "unless-stopped"
  network_mode = "bridge"
  networks_advanced {
    name = docker_network.open-telemetry-network.name
  }
  ports {
    internal = 16686
  }
  ports {
    internal = 4317
  }
  env = [
    "METRICS_STORAGE_TYPE=prometheus"
  ]
}

# grafana container

resource "docker_container" "grafana" {
  name    = "grafana"
  image   = "grafana/grafana:10.4.3"
  network_mode = "bridge"
  networks_advanced {
    name = docker_network.open-telemetry-network.name
  }
  memory  = 100
  restart = "unless-stopped"
  env     = ["GF_INSTALL_PLUGINS=grafana-opensearch-datasource"]
  volumes {
    host_path      = "${var.project_path}${var.seperator}src${var.seperator}grafana${var.seperator}grafana.ini"
    container_path = "/etc/grafana/grafana.ini"

  }
  volumes {
    host_path      = "${var.project_path}${var.seperator}src${var.seperator}grafana${var.seperator}provisioning${var.seperator}"
    container_path = "/etc/grafana/provisioning/"
  }
  ports {
    internal = 3000
  }

}

# opentelemetry collector container

resource "docker_container" "otelcol" {
  name       = "otelcol"
  image      = "otel/opentelemetry-collector-contrib:0.102.1"
  depends_on = [docker_container.jaeger]
  network_mode = "bridge"
  networks_advanced {
    name = docker_network.open-telemetry-network.name
  }
  memory     = 200
  restart    = "unless-stopped"
  command    = ["--config=/etc/otelcol-config.yml", "--config=/etc/otelcol-config-extras.yml"
  ]
  volumes {
    host_path      = "${var.project_path}${var.seperator}src${var.seperator}otelcollector${var.seperator}otelcol-config.yml"
    container_path = "/etc/otelcol-config.yml"
  }
  volumes {
    host_path      = "${var.project_path}${var.seperator}src${var.seperator}otelcollector${var.seperator}otelcol-config-extras.yml"
    container_path = "/etc/otelcol-config-extras.yml"
  }
  volumes {
    host_path = "/var/run/docker.sock"
    container_path = "/var/run/docker.sock"
  }
  ports {
    internal = 4317
  }
  ports {
    internal = 4318
  }
  env = ["ENVOY_PORT=8080",
          "OTEL_COLLECTOR_HOST=otelcol",
          "OTEL_COLLECTOR_PORT_GRPC=4317",
          "OTEL_COLLECTOR_PORT_HTTP=4318"
          ]

}

# prometheus container

resource "docker_container" "prometheus" {
  name  = "prometheus"
  image = "quay.io/prometheus/prometheus:v2.52.0"
  command = ["--web.console.templates=/etc/prometheus/consoles", 
    "--web.console.libraries=/etc/prometheus/console_libraries", 
    "--storage.tsdb.retention.time=1h",
    "--config.file=/etc/prometheus/prometheus-config.yaml", 
    "--storage.tsdb.path=/prometheus", 
    "--web.enable-lifecycle", 
    "--web.route-prefix=/", 
    "--enable-feature=exemplar-storage", 
    "--enable-feature=otlp-write-receiver"
  ]
  network_mode = "bridge"
  networks_advanced {
    name = docker_network.open-telemetry-network.name
  }
  volumes {
    host_path      = "${var.project_path}${var.seperator}src${var.seperator}prometheus${var.seperator}prometheus-config.yaml"
    container_path = "/etc/prometheus/prometheus-config.yaml"
  }
  memory  = 300
  restart = "unless-stopped"
  ports {
    internal = 9090
    external = 9090
  }
}

# open search container

resource "docker_container" "opensearch" {
  name    = "opensearch"
  image   = "opensearchproject/opensearch:1.2.0"
  network_mode = "bridge"
  networks_advanced {
    name = docker_network.open-telemetry-network.name
  }
  memory  = 1000
  restart = "unless-stopped"
  env = [
    "cluster.name=demo-cluster",
    "node.name=demo-node",
    "bootstrap.memory_lock=true",
    "discovery.type=single-node",
    "OPENSEARCH_JAVA_OPTS=-Xms300m -Xmx300m",
    "DISABLE_INSTALL_DEMO_CONFIG=true",
    "DISABLE_SECURITY_PLUGIN=true"
  ]
  ports {
    internal = 9200
  }
}
# test container

#frontend test container

resource "docker_container" "namfrontendTests" {
  name       = "frontend-tests"
  image      = "ghcr.io/open-telemetry/demo:latest-frontend-tests"
  depends_on = [docker_container.frontend]
  network_mode = "bridge"
  networks_advanced {
    name = docker_network.open-telemetry-network.name
  }
  volumes {
    host_path      = "${var.project_path}${var.seperator}src${var.seperator}frontend${var.seperator}cypress${var.seperator}videos"
    container_path = "/app/cypress/videos"
  }
  volumes {
    host_path      = "${var.project_path}${var.seperator}src${var.seperator}frontend${var.seperator}cypress${var.seperator}screenshots"
    container_path = "/app/cypress/screenshots"
  }
  env = [
    "CYPRESS_baseUrl=http://frontend:8080",
    "FRONTEND_ADDR=frontend:8080",
  "NODE_ENV=production"]
}

# tracebased test container

resource "docker_container" "traceBasedTests" {
  name  = "traceBasedTests"
  image = "ghcr.io/open-telemetry/demo:latest-traceBasedTests"
  depends_on = [docker_container.tracetest-server,
    docker_container.frontend,
    docker_container.adservice-container,
    docker_container.cartservice-container,
    docker_container.checkoutservice-container,
    docker_container.currencyservice-container,
    docker_container.emailservice-container,
    docker_container.paymentservice,
    docker_container.productcatalogservice,
    docker_container.recommendationservice,
    docker_container.shippingservice,
    docker_container.quoteservice,
    docker_container.accountingservice-container,
    docker_container.frauddetectionservice-container,
  docker_container.flagd]
  network_mode = "bridge"
  networks_advanced {
    name = docker_network.open-telemetry-network.name
  }
  env = [
    "AD_SERVICE_ADDR=adservice:9555",
    "CART_SERVICE_ADDR =  cartservice:7070",
    "CHECKOUT_SERVICE_ADDR = checkoutservice:5050",
    "CURRENCY_SERVICE_ADDR = currencyservice:7001",
    "EMAIL_SERVICE_ADDR = http://emailservice:6060",
    "FRONTEND_ADDR = frontend:8080",
    "PAYMENT_SERVICE_ADDR = paymentservice:50051",
    "PRODUCT_CATALOG_SERVICE_ADDR = productcatalogservice:3550",
    "RECOMMENDATION_SERVICE_ADDR = recommendationservice:9001",
    "SHIPPING_SERVICE_ADDR = shippingservice:50050",
    "KAFKA_SERVICE_ADDR = kafka:9092"
  ]
  volumes {
    host_path      = "${var.project_path}${var.seperator}test${var.seperator}tracetesting"
    container_path = "/app/test/tracetesting"
  }
  volumes {
    host_path      = "${var.project_path}${var.seperator}pb"
    container_path = "/app/pb"
  }

}

# tracetest server container

resource "docker_container" "tracetest-server" {
  name       = "tracetest-server"
  image      = "kubeshop/tracetest:v1.3.0"
  depends_on = [docker_container.tracetest-postgres, docker_container.otelcol, docker_container.frontendproxy]
  network_mode = "bridge"
  networks_advanced {
    name = docker_network.open-telemetry-network.name
  }
  volumes {
    host_path      = "${var.project_path}${var.seperator}test${var.seperator}tracetesting${var.seperator}tracetest-config.yaml"
    container_path = "/app/tracetest.yaml"
  }
  volumes {
    host_path      = "${var.project_path}${var.seperator}test${var.seperator}tracetesting${var.seperator}tracetest-provision.yaml"
    container_path = "/app/provision.yaml"
  }
  command = ["--provisioning-file /app/provision.yaml"]
  ports {
    internal = 11633
    external = 11633
  }
  healthcheck {
    test     = ["wget", "--spider", "localhost:11633"]
    interval = "1s"
    timeout  = "3s"
    retries  = 60
  }

}

#tracetest postgress container

resource "docker_container" "tracetest-postgres" {
  name  = "tracetest-postgres"
  image = "postgres:16.3"
  env = [
    "POSTGRES_PASSWORD= postgres",
    "POSTGRES_USER= postgres"
  ]
  network_mode = "bridge"
  networks_advanced {
    name = docker_network.open-telemetry-network.name
  }
  healthcheck {
    test     = ["pg_isready", "-U", "$$POSTGRES_USER", "-d", "$$POSTGRES_DB"]
    interval = "1s"
    timeout  = "5s"
    retries  = 60
  }
  ports {
    internal = 5432
  }

}






