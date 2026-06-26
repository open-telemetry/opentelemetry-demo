// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using Microsoft.Extensions.Logging;
using Oteldemo;

namespace Accounting
{
    internal static partial class Log
    {
        [LoggerMessage(
            Level = LogLevel.Information,
            EventName = "OrderReceived",
            Message = "Order details: {@OrderResult}.")]
        public static partial void OrderReceivedMessage(ILogger logger, OrderResult orderResult);

        [LoggerMessage(
            Level = LogLevel.Information,
            EventName = "KafkaConnecting",
            Message = "Connecting to Kafka: {servers}")]
        public static partial void KafkaConnecting(ILogger logger, string servers);

        [LoggerMessage(
            Level = LogLevel.Error,
            EventName = "KafkaConsumeError",
            Message = "Consume error: {reason}")]
        public static partial void ConsumeError(ILogger logger, Exception exception, string reason);

        [LoggerMessage(
            Level = LogLevel.Information,
            EventName = "ConsumerClosing",
            Message = "Closing consumer")]
        public static partial void ConsumerClosing(ILogger logger);

        [LoggerMessage(
            Level = LogLevel.Information,
            EventName = "DuplicateOrderSkipped",
            Message = "Duplicate order received, skipping.")]
        public static partial void DuplicateOrderSkipped(ILogger logger);

        [LoggerMessage(
            Level = LogLevel.Error,
            EventName = "OrderParsingFailed",
            Message = "Order parsing failed:")]
        public static partial void OrderParsingFailed(ILogger logger, Exception exception);
    }
}
