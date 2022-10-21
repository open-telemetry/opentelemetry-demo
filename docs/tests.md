# Tests

Currently, the repository includes E2E tests for both the frontend and backend services.
For the Frontend we are using [Cypress](https://www.cypress.io/) execute the
different flows in the webstore.
While the backend services use [AVA](https://avajs.dev) as the main testing framework.

To run the test you can simply run `make run-tests` at the root directory.

In case you need to run a specific suite of tests you can execute
`docker compose run frontendTests` for the frontend tests or
`docker compose run integrationTests` for the backend tests.
