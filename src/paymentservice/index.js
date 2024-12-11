// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
const Bugsnag = require("@bugsnag/js");
// const BugsnagPerformance = require("@bugsnag/browser-performance");

const grpc = require("@grpc/grpc-js");
const protoLoader = require("@grpc/proto-loader");
const health = require("grpc-js-health-check");
const opentelemetry = require("@opentelemetry/api");

const charge = require("./charge");
const logger = require("./logger");

Bugsnag.start({ apiKey: "01b9eac8f217a08829952da129612990" });
// BugsnagPerformance.start({
//   apiKey: "01b9eac8f217a08829952da129612990",
// });

async function chargeServiceHandler(call, callback) {
  const span = opentelemetry.trace.getActiveSpan();
  Bugsnag.notify(new Error("Test error"));

  try {
    const amount = call.request.amount;
    span.setAttributes({
      "app.payment.amount": parseFloat(`${amount.units}.${amount.nanos}`),
    });
    logger.info({ request: call.request }, "Charge request received.");

    const response = await charge.charge(call.request);
    callback(null, response);
  } catch (err) {
    logger.warn({ err });

    span.recordException(err);
    span.setStatus({ code: opentelemetry.SpanStatusCode.ERROR });

    callback(err);
  }
}

async function closeGracefully(signal) {
  server.forceShutdown();
  process.kill(process.pid, signal);
}

const otelDemoPackage = grpc.loadPackageDefinition(
  protoLoader.loadSync("demo.proto")
);
const server = new grpc.Server();

server.addService(
  health.service,
  new health.Implementation({
    "": health.servingStatus.SERVING,
  })
);

server.addService(otelDemoPackage.oteldemo.PaymentService.service, {
  charge: chargeServiceHandler,
});

server.bindAsync(
  `0.0.0.0:${process.env["PAYMENT_SERVICE_PORT"]}`,
  grpc.ServerCredentials.createInsecure(),
  (err, port) => {
    if (err) {
      return logger.error({ err });
    }

    logger.info(`PaymentService gRPC server started on port ${port}`);
    server.start();
  }
);

process.once("SIGINT", closeGracefully);
process.once("SIGTERM", closeGracefully);
