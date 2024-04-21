// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
const {
	LoggerProvider,
	SimpleLogRecordProcessor,
	ConsoleLogRecordExporter,
} = require("@opentelemetry/sdk-logs");

const loggerProvider = new LoggerProvider();
loggerProvider.addLogRecordProcessor(
	new SimpleLogRecordProcessor(new ConsoleLogRecordExporter())
);

module.exports = loggerProvider.getLogger("paymentservice", "1.0.0");