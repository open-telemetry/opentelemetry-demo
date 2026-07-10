// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
using System;
using System.Collections.Generic;
using System.Net.WebSockets;
using System.Threading.Tasks;

using OpenTelemetry.OpAmp.Client;
using OpenTelemetry.OpAmp.Client.Settings;
using OpenTelemetry.Resources;

internal static class OpAmpClientSetup
{
    private static readonly HashSet<string> IdentifyingKeys = new()
    {
        "service.name",
        "service.version",
        "service.instance.id",
    };

    public static async Task<OpAmpClient> StartAsync(string endpoint, Resource resource)
    {
        var client = new OpAmpClient(opts =>
        {
            opts.ConnectionType = ConnectionType.WebSocket;
            opts.ServerUrl = new Uri(endpoint);

            foreach (var attribute in resource.Attributes)
            {
                var value = attribute.Value?.ToString();
                if (value is null)
                {
                    continue;
                }

                if (IdentifyingKeys.Contains(attribute.Key))
                {
                    opts.Identification.AddIdentifyingAttribute(attribute.Key, value);
                }
                else
                {
                    opts.Identification.AddNonIdentifyingAttribute(attribute.Key, value);
                }
            }

            // The demo's OpAMP server uses a self-signed certificate, so skip
            // certificate validation for the demo's wss:// connection.
            opts.ClientWebSocketFactory = () =>
            {
                var socket = new ClientWebSocket();
                socket.Options.RemoteCertificateValidationCallback =
                    (sender, certificate, chain, sslPolicyErrors) => true;
                return socket;
            };
        });

        await client.StartAsync();
        return client;
    }
}
