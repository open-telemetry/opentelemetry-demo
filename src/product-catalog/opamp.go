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
	"go.opentelemetry.io/otel/sdk/resource"
)

var opampIdentifyingKeys = map[string]bool{
	"service.name":        true,
	"service.version":     true,
	"service.instance.id": true,
}

func startOpAmpClient(ctx context.Context) (client.OpAMPClient, error) {
	endpoint := os.Getenv("OPAMP_SERVER_ENDPOINT")
	if endpoint == "" {
		return nil, nil
	}

	res, err := resource.New(ctx,
		resource.WithFromEnv(),
		resource.WithTelemetrySDK(),
		resource.WithHost(),
		resource.WithContainer(),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to build resource: %w", err)
	}

	var identifying, nonIdentifying []*protobufs.KeyValue
	for _, attr := range res.Attributes() {
		kv := &protobufs.KeyValue{
			Key: string(attr.Key),
			Value: &protobufs.AnyValue{
				Value: &protobufs.AnyValue_StringValue{StringValue: attr.Value.Emit()},
			},
		}
		if opampIdentifyingKeys[string(attr.Key)] {
			identifying = append(identifying, kv)
		} else {
			nonIdentifying = append(nonIdentifying, kv)
		}
	}

	opampClient := client.NewWebSocket(nil)

	err = opampClient.SetAgentDescription(&protobufs.AgentDescription{
		IdentifyingAttributes:    identifying,
		NonIdentifyingAttributes: nonIdentifying,
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
