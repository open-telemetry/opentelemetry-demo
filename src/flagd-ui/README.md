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
    ...
  }
}
```

You can also write a new settings file by sending a new configuration inside
the `data` field of a POST request body.

Bear in mind that _all_ the data will be rewritten by this write operation.

```sh
$ curl --header "Content-Type: application/json" \
  --request POST \
  --data '{"data": {"$schema":"https://flagd.dev/schema/v0/flags.json","flags":{"adFailure":{"defaultVariant":"on","description":"Fail ad service","state":"ENABLED","variants":{"off":false,"on":true}}...' \
  http://localhost:8080/feature/api/write
```

In addition to the `/read` and `/write` endpoint, we also offer these endpoint
to stay compatible with the old version of Flagd-ui:

* `/read-file` (`GET`)
* `/write-to-file` (`POST`)
