// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
package main

import (
	"context"
	"crypto/rand"
	"crypto/tls"
	"encoding/hex"
	"fmt"
	"os"
	"strconv"

	"github.com/open-telemetry/opamp-go/client"
	"github.com/open-telemetry/opamp-go/client/types"
	"github.com/open-telemetry/opamp-go/protobufs"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/sdk/resource"
)

var opampIdentifyingKeys = map[string]bool{
	"service.name":        true,
	"service.instance.id": true,
	"service.namespace":   true,
}

const (
	opampServerEndpointEnv              = "OPAMP_SERVER_ENDPOINT"
	opampServerTLSInsecureSkipVerifyEnv = "OPAMP_SERVER_TLS_INSECURE_SKIP_VERIFY"
)

func startOpAmpClient(ctx context.Context) (client.OpAMPClient, error) {
	endpoint := os.Getenv(opampServerEndpointEnv)
	if endpoint == "" {
		return nil, nil
	}

	var instanceUID types.InstanceUid
	if _, err := rand.Read(instanceUID[:]); err != nil {
		return nil, fmt.Errorf("failed to generate instance uid: %w", err)
	}

	res, err := resource.New(ctx,
		resource.WithFromEnv(),
		resource.WithTelemetrySDK(),
		resource.WithHost(),
		resource.WithContainer(),
		resource.WithAttributes(attribute.String("service.instance.id", hex.EncodeToString(instanceUID[:]))),
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

	startSettings := types.StartSettings{
		OpAMPServerURL: endpoint,
		InstanceUid:    instanceUID,
		Capabilities:   protobufs.AgentCapabilities_AgentCapabilities_ReportsHealth,
	}

	skipTLSCertificateVerificationEnv := os.Getenv(opampServerTLSInsecureSkipVerifyEnv)
	skipTLSCertificateVerification, err := strconv.ParseBool(skipTLSCertificateVerificationEnv)
	if err != nil && skipTLSCertificateVerificationEnv != "" {
		return nil, fmt.Errorf("failed to parse %s: %w", opampServerTLSInsecureSkipVerifyEnv, err)
	}
	if skipTLSCertificateVerification {
		// The demo's OpAMP server uses a self-signed certificate for wss://.
		startSettings.TLSConfig = &tls.Config{InsecureSkipVerify: true}
	}

	err = opampClient.Start(ctx, startSettings)
	if err != nil {
		return nil, fmt.Errorf("failed to start OpAMP client: %w", err)
	}

	return opampClient, nil
}
