// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
const grpc = require("@grpc/grpc-js");
const protoLoader = require("@grpc/proto-loader");
const health = require("grpc-js-health-check");
const opentelemetry = require("@opentelemetry/api");
const { SeverityNumber } = require("@opentelemetry/api-logs");

const charge = require("./charge");
const logger = require("./logger");

async function chargeServiceHandler(call, callback) {
	const span = opentelemetry.trace.getActiveSpan();

	try {
		const amount = call.request.amount;
		span.setAttributes({
			"app.payment.amount": parseFloat(`${amount.units}.${amount.nanos}`),
		});
		logger.emit({
			severityNumber: SeverityNumber.INFO,
			severityText: "INFO",
			body: "Charge request received.",
			attributes: { request: call.request },
		});

		const response = await charge.charge(call.request);
		callback(null, response);
	} catch (err) {
		logger.emit({
			severityNumber: SeverityNumber.WARN,
			severityText: "ERROR",
			body: "Charge request failed.",
			attributes: { request: call.request },
		});

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

		logger.emit({
			severityNumber: SeverityNumber.INFO,
			severityText: "INFO",
			body: `PaymentService gRPC server started on port ${port}.`,
		});
		server.start();
	}
);

process.once('SIGINT', closeGracefully);
process.once('SIGTERM', closeGracefully);
