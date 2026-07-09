// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
package main

import (
	"context"
	"crypto/rand"
	"crypto/tls"
	"fmt"
	"os"

	"github.com/open-telemetry/opamp-go/client"
	"github.com/open-telemetry/opamp-go/client/types"
	"github.com/open-telemetry/opamp-go/protobufs"
)

// startOpAmpClient reports this service's status to the demo's OpAMP server,
// demonstrating OpAMP as a control plane for an SDK-instrumented application
// alongside the Collector. It returns a nil client (and no error) when
// OPAMP_SERVER_ENDPOINT is not set, i.e. when running without the observability
// stack.
func startOpAmpClient(ctx context.Context, serviceName string) (client.OpAMPClient, error) {
	endpoint := os.Getenv("OPAMP_SERVER_ENDPOINT")
	if endpoint == "" {
		return nil, nil
	}

	opampClient := client.NewWebSocket(nil)

	err := opampClient.SetAgentDescription(&protobufs.AgentDescription{
		IdentifyingAttributes: []*protobufs.KeyValue{
			{
				Key:   "service.name",
				Value: &protobufs.AnyValue{Value: &protobufs.AnyValue_StringValue{StringValue: serviceName}},
			},
		},
		NonIdentifyingAttributes: []*protobufs.KeyValue{
			{
				Key:   "telemetry.sdk.language",
				Value: &protobufs.AnyValue{Value: &protobufs.AnyValue_StringValue{StringValue: "go"}},
			},
		},
	})
	if err != nil {
		return nil, fmt.Errorf("failed to set agent description: %w", err)
	}

	if err := opampClient.SetHealth(&protobufs.ComponentHealth{Healthy: true}); err != nil {
		return nil, fmt.Errorf("failed to set health: %w", err)
	}

	var instanceUID types.InstanceUid
	if _, err := rand.Read(instanceUID[:]); err != nil {
		return nil, fmt.Errorf("failed to generate instance uid: %w", err)
	}

	err = opampClient.Start(ctx, types.StartSettings{
		OpAMPServerURL: endpoint,
		InstanceUid:    instanceUID,
		// The demo's OpAMP server uses a self-signed certificate, so skip
		// certificate validation for the demo's wss:// connection.
		TLSConfig:    &tls.Config{InsecureSkipVerify: true},
		Capabilities: protobufs.AgentCapabilities_AgentCapabilities_ReportsHealth,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to start OpAMP client: %w", err)
	}

	return opampClient, nil
}
