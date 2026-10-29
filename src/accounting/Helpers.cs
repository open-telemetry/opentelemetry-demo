// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using System.Collections;

namespace Accounting
{
    internal static class Helpers
    {
        private static List<string> RelevantPrefixes = ["DOTNET_", "CORECLR_", "OTEL_", "KAFKA_"];

        // Values of matching variables are masked when printed, e.g.
        // OTEL_EXPORTER_OTLP_HEADERS / OTEL_EXPORTER_OTLP_TRACES_HEADERS (API keys, bearer tokens).
        private static List<string> SensitiveKeyParts = ["HEADERS", "PASSWORD", "SECRET", "TOKEN", "API_KEY"];

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
            key is not null && SensitiveKeyParts.Any(part => key.Contains(part, StringComparison.InvariantCultureIgnoreCase));
    }
}
