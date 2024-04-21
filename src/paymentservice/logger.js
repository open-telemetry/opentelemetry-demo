// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
const {
	LoggerProvider,
	SimpleLogRecordProcessor,
	ConsoleLogRecordExporter,
} = require("@opentelemetry/sdk-logs");
import { logs } from "@opentelemetry/api-logs";

const loggerProvider = new LoggerProvider();
loggerProvider.addLogRecordProcessor(
	new SimpleLogRecordProcessor(new ConsoleLogRecordExporter())
);
logs.setGlobalLoggerProvider(loggerProvider);

module.exports = logs.getLogger("paymentservice", "1.0.0");