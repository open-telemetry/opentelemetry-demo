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
