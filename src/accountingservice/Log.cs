using Microsoft.Extensions.Logging;
using Oteldemo;

namespace AccountingService
{
    internal static partial class Log
    {
        [LoggerMessage(
            Level = LogLevel.Information,
            Message = "Order details: {@OrderResult}.")]
        public static partial void LogOrderReceivedMessage(ILogger logger, OrderResult orderResult);
    }
}
