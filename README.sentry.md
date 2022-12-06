# Sentry-specific Changes

To run the demo locally, configure Sentry DSN values for every service in the demo in `.env.sentry` file, and use our `docker-compose` wrapper:

```sh
# Copy the example file
cp .env.sentry.example .env.sentry

# Update Sentry DSN values in `.env.sentry`

# Start docker-compose
./compose.sh up
```
