# Sentry-specific Changes

To run the demo locally, configure Sentry DSN values for every service in the demo in `.env.sentry` file, and use our `docker-compose` wrapper:

```sh
# Copy the example file
cp .env.sentry.example .env.sentry

# Update Sentry DSN values in `.env.sentry`

# Start docker-compose
./compose.sh up
```

You can add an optional `docker-compose.override.yml` file if you want to override various values for local development or testing.

Compose configuration will be read (and overridden) in the following order:

1. `docker-compose.yml`
2. `docker-compose.sentry.yml`
3. `docker-compose.override.yml`

So the values in `docker-compose.override.yml` will "win" over the corresponding values in the other files.

## Deploying the Demo

See [./deploy/README.md](./deploy/README.md) for more details.
