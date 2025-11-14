# Flagd-ui

This application provides a user interface for configuring the feature
flags of the flagd service.

This is a [Phoenix](https://www.phoenixframework.org/) project.

## Running the application

The application can be run with the rest of the demo using the documented
[docker compose or make commands](https://opentelemetry.io/docs/demo/#running-the-demo).

## Local development

* Run `mix setup` to install and setup dependencies
* Create a `data` folder: `mkdir data`.
* Copy [../flagd/demo.flagd.json](../flagd/demo.flagd.json) to `./data/demo.flagd.json`
  * `cp ../flagd/demo.flagd.json ./data/demo.flagd.json`
* Start Phoenix endpoint with `mix phx.server` or inside IEx with `iex -S mix phx.server`

Now you can visit `localhost:4000` from your browser.

## Programmatic use through the API

This service exposes a REST API to ease its usage in a programmatic way for
power users.

You can read the current configuration using this HTTP call:

```json
$ curl localhost:8080/feature/api/read | jq

{
  "flags": {
    "adFailure": {
      "defaultVariant": "off",
      "description": "Fail ad service",
      "state": "ENABLED",
      "variants": {
        "off": false,
        "on": true
      }
    },
    "adHighCpu": {
      "defaultVariant": "off",
      "description": "Triggers high cpu load in the ad service",
      "state": "ENABLED",
      "variants": {
        "off": false,
        "on": true
      }
    },
    "adManualGc": {
      "defaultVariant": "off",
      "description": "Triggers full manual garbage collections in the ad service",
      "state": "ENABLED",
      "variants": {
        "off": false,
        "on": true
      }
    },
    "cartFailure": {
      "defaultVariant": "off",
      "description": "Fail cart service",
      "state": "ENABLED",
      "variants": {
        "off": false,
        "on": true
      }
    },
    "emailMemoryLeak": {
      "defaultVariant": "off",
      "description": "Memory leak in the email service.",
      "state": "ENABLED",
      "variants": {
        "10000x": 10000,
        "1000x": 1000,
        "100x": 100,
        "10x": 10,
        "1x": 1,
        "off": 0
      }
    },
    "imageSlowLoad": {
      "defaultVariant": "off",
      "description": "slow loading images in the frontend",
      "state": "ENABLED",
      "variants": {
        "10sec": 10000,
        "5sec": 5000,
        "off": 0
      }
    },
    "kafkaQueueProblems": {
      "defaultVariant": "off",
      "description": "Overloads Kafka queue while simultaneously introducing a consumer side delay leading to a lag spike",
      "state": "ENABLED",
      "variants": {
        "off": 0,
        "on": 100
      }
    },
    "llmInaccurateResponse": {
      "defaultVariant": "off",
      "description": "LLM returns an inaccurate product summary for product ID L9ECAV7KIM",
      "state": "ENABLED",
      "variants": {
        "off": false,
        "on": true
      }
    },
    "llmRateLimitError": {
      "defaultVariant": "off",
      "description": "LLM intermittently returns a rate limit error",
      "state": "ENABLED",
      "variants": {
        "off": false,
        "on": true
      }
    },
    "loadGeneratorFloodHomepage": {
      "defaultVariant": "off",
      "description": "Flood the frontend with a large amount of requests.",
      "state": "ENABLED",
      "variants": {
        "off": 0,
        "on": 100
      }
    },
    "paymentFailure": {
      "defaultVariant": "off",
      "description": "Fail payment service charge requests n%",
      "state": "ENABLED",
      "variants": {
        "10%": 0.1,
        "100%": 1,
        "25%": 0.25,
        "50%": 0.5,
        "75%": 0.75,
        "90%": 0.95,
        "off": 0
      }
    },
    "paymentUnreachable": {
      "defaultVariant": "off",
      "description": "Payment service is unavailable",
      "state": "ENABLED",
      "variants": {
        "off": false,
        "on": true
      }
    },
    "productCatalogFailure": {
      "defaultVariant": "off",
      "description": "Fail product catalog service on a specific product",
      "state": "ENABLED",
      "variants": {
        "off": false,
        "on": true
      }
    },
    "recommendationCacheFailure": {
      "defaultVariant": "off",
      "description": "Fail recommendation service cache",
      "state": "ENABLED",
      "variants": {
        "off": false,
        "on": true
      }
    }
  }
}
```

You can also write a new settings file by sending a new configuration inside
the `data` field of a POST request body.

Bear in mind that _all_ the data will be rewritten by this write operation.

```sh
$ curl --header "Content-Type: application/json" \
  --request POST \
  --data '{"data": {"productCatalogFailure": {"defaultVariant": "off", "description": "Fail product catalog service on a specific product"}}...' \
  http://localhost:8080/feature/api/write
```

In addition to the `/read` and `/write` endpoint, we also offer these endpoint
to stay compatible with the old version of Flagd-ui:

* `/read-file` (`GET`)
* `/write-to-file` (`POST`)
