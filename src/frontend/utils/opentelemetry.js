const process = require("process")
const opentelemetry = require("@opentelemetry/sdk-node")
const { getNodeAutoInstrumentations } = require("@opentelemetry/auto-instrumentations-node")
const { OTLPTraceExporter } = require("@opentelemetry/exporter-trace-otlp-grpc")

// configure the SDK to export telemetry data to the console
// enable all auto-instrumentations from the meta package
const sdk = new opentelemetry.NodeSDK({
  autoDetectResources: true,
  instrumentations: [
    getNodeAutoInstrumentations({
      // Each of the auto-instrumentations
      // can have config set here or you can
      // npm install each individually and not use the auto-instruments
      "@opentelemetry/instrumentation-http": {
        ignoreIncomingPaths: [
          // Pattern match to filter endpoints
          // that you really want to stop altogether
          "/ping",

          // You can filter conditionally
          // Next.js gets a little too chatty
          // if you trace all the incoming requests
          ...(process.env.NODE_ENV !== "production"
            ? [/^\/_next\/static.*/]
            : []),
        ],

        // This gives your request spans a more meaningful name
        // than `HTTP GET`
        requestHook: (span, request) => {
          span.setAttributes({
            name: `${request.method} ${request.url || request.path}`,
          })
        },

        // Re-assign the root span's attributes
        startIncomingSpanHook: (request) => {
          return {
            name: `${request.method} ${request.url || request.path}`,
            "request.path": request.url || request.path,
          }
        },
      }
    }),
  ],
  traceExporter: new OTLPTraceExporter(),
})

// initialize the SDK and register with the OpenTelemetry API
// this enables the API to record telemetry
sdk
  .start()
  .then(() => console.log("Tracing initialized"))
  .catch((error) =>
    console.log("Error initializing tracing and starting server", error)
  )

// gracefully shut down the SDK on process exit
process.on("SIGTERM", () => {
  sdk
    .shutdown()
    .then(() => console.log("Tracing terminated"))
    .catch((error) => console.log("Error terminating tracing", error))
    .finally(() => process.exit(0))
})
