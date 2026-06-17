# Frontend service

The frontend is a [Next.js](https://nextjs.org/) application that is composed
by two layers.

1. Client side application. Which renders the components for the OTEL webstore.
2. API layer. Connects the client to the backend services by exposing REST endpoints.

## Build Locally

By running `docker compose up` at the root of the project you'll have access to
the frontend client by going to <http://localhost:8080/>.

## Local development

Currently, the easiest way to run the frontend for local development is to execute

```shell
docker compose run --service-ports -e NODE_ENV=development --volume $(pwd)/src/frontend:/app --volume $(pwd)/pb:/app/pb --user node --entrypoint sh frontend
```

from the root folder.

It will start all of the required backend services
and within the container simply run `npm run dev`.
After that the app should be available at <http://localhost:8080/>.

## Embrace Web SDK

The browser frontend initializes the Embrace Web SDK from public Next.js env
vars. DevOps should provide these values in deployed environments so they can be
changed without application source changes.

```shell
NEXT_PUBLIC_EMBRACE_APP_ID=omhea
NEXT_PUBLIC_EMBRACE_APP_VERSION=2.2.0
NEXT_PUBLIC_EMBRACE_ENVIRONMENT=demo
NEXT_PUBLIC_ENABLE_DEMO_ISSUES=true
NEXT_PUBLIC_AUTO_DEMO_ISSUES=false
```

`NEXT_PUBLIC_EMBRACE_APP_ID` is not a secret, but real secret tokens should
never be committed. If the app ID is omitted, the storefront still runs and logs
a browser warning that Embrace initialization was skipped.

Manual demo issue URLs:

- `/?run_source=manual&user_persona=manual_tester`
- `/?issue_variant=profile_preferences_error&user_persona=broken_session_user`
- `/product/OLJCESPC7Z?issue_variant=product_recommendation_error&user_persona=broken_session_user`
- `/cart?issue_variant=cart_price_mismatch&user_persona=cart_reconciler`
- `/cart?issue_variant=checkout_validation_error&user_persona=frustrated_buyer`

Demo issues fire at most once per browser session. Automatic issue injection is
only enabled when `NEXT_PUBLIC_AUTO_DEMO_ISSUES=true` and the Embrace
environment is `local`, `demo`, or `internal`; it is never automatic in
`production`. Playwright traffic generation is intentionally deferred to a
future repo.
