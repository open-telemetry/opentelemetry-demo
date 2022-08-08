# Frontend service

The frontend is a Next.js application that is composed by two layers.
1. Client side application. Which renders the components for the OTEL webstore.
2. API layer. Connects the client to the gRPC services by exposing REST endpoints.

## Build Locally

By running `docker-compose up` at the root of the project you'll have access to the
frontend client by going to <localhost:8081>.

## Local development

Currently, the easiest way to run the frontend for local development is to execute
`docker-compose run --service-ports -e NODE_ENV=development --volume $(pwd)/src/frontend:/app --volume $(pwd)/pb:/app/pb frontend sh`
from the root folder.

It will start all of the required backend services and within the container simply run
`npm run dev` after that the app should be available at <localhost:8081>

## Building the Docker image

Before committing your changes to the repo,
run `docker-compose build frontend` to validate that the image works as expected.
