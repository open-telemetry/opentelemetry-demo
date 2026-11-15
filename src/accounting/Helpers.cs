// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using System.Collections;
using System.Text.RegularExpressions;

namespace Accounting
{
    internal static partial class Helpers
    {
        private static List<string> RelevantPrefixes = ["DOTNET_", "CORECLR_", "OTEL_", "KAFKA_"];

        // Values of matching variables are masked when printed, e.g. OTEL_EXPORTER_OTLP_HEADERS (API keys, bearer tokens).
        // Same pattern the OpenTelemetry .NET auto-instrumentation uses to hide secrets when it logs environment variables:
        // https://github.com/open-telemetry/opentelemetry-dotnet-instrumentation/blob/d4ee69cb4e30d42caf83a1a33962879643157156/src/OpenTelemetry.AutoInstrumentation.Native/regex_utils.cpp#L247
        [GeneratedRegex(@"(?:^|_)(API|TOKEN|SECRET|KEY|PASSWORD|PASS|PWD|HEADERS?|CREDENTIALS)(?:_|=|$)", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant)]
        private static partial Regex SecretsPattern();

        public static IEnumerable<DictionaryEntry> FilterRelevant(this IDictionary envs)
        {
            foreach (DictionaryEntry env in envs)
            {
                foreach (var prefix in RelevantPrefixes)
                {
                    if (env.Key.ToString()?.StartsWith(prefix, StringComparison.InvariantCultureIgnoreCase) ?? false)
                    {
                        yield return env;
                    }
                }
            }
        }

        public static void OutputInOrder(this IEnumerable<DictionaryEntry> envs)
        {
            foreach (var env in envs.OrderBy(x => x.Key))
            {
                Console.WriteLine(IsSensitive(env.Key.ToString()) ? new DictionaryEntry(env.Key, "[REDACTED]") : env);
            }
        }

        private static bool IsSensitive(string? key) =>
            key is not null && SecretsPattern().IsMatch(key);
    }
}
