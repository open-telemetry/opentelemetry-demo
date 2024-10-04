# Flagd-ui

This application provides a user interface for configuring the feature
flags of the flagd service.

This is a [Next.js](https://nextjs.org/) project.

## Running the application

The application can be run with the rest of the demo using the documented
docker compose or make commands.

## Local development

To run the app locally for development you must copy
`src/flagd/demo.flagd.json` into `src/flagd-ui/data/demo.flagd.json`
(create the directory and file if they do not exist yet). Make sure you're
in the `src/flagd-ui` directory and run
the following command:

```bash
npm run dev
```

Then you must navigate to `localhost:4000/feature`.
