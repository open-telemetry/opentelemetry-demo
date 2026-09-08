// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
package main

import (
	"context"
	"crypto/rand"
	"crypto/tls"
	"encoding/hex"
	"fmt"
	"log/slog"
	"os"
	"strconv"
	"time"

	"github.com/open-telemetry/opamp-go/client"
	"github.com/open-telemetry/opamp-go/client/types"
	"github.com/open-telemetry/opamp-go/protobufs"
	"go.opentelemetry.io/otel/sdk/resource"
)

const (
	opAMPServerEndpointEnv              = "OPAMP_SERVER_ENDPOINT"
	opAMPServerTLSInsecureSkipVerifyEnv = "OPAMP_SERVER_TLS_INSECURE_SKIP_VERIFY"
	otelResourceAttributesEnv           = "OTEL_RESOURCE_ATTRIBUTES"
)

type opAMPIdentity struct {
	instanceUID types.InstanceUid
}

type opAMPLogger struct {
	logger *slog.Logger
}

func (l opAMPLogger) Debugf(ctx context.Context, format string, args ...any) {
	l.logger.DebugContext(ctx, fmt.Sprintf(format, args...))
}

func (l opAMPLogger) Errorf(ctx context.Context, format string, args ...any) {
	l.logger.ErrorContext(ctx, fmt.Sprintf(format, args...))
}

func prepareOpAMPIdentity() (*opAMPIdentity, error) {
	endpoint := os.Getenv(opAMPServerEndpointEnv)
	if endpoint == "" {
		return nil, nil
	}

	var instanceUID types.InstanceUid
	if _, err := rand.Read(instanceUID[:]); err != nil {
		return nil, fmt.Errorf("generate instance UID: %w", err)
	}

	res, err := resource.New(context.Background(), resource.WithFromEnv())
	if err != nil {
		logger.Warn("Read partial resource attributes for OpAMP", slog.Any("error", err))
	}
	if res == nil {
		res = resource.Empty()
	}
	if serviceInstanceID, ok := res.Set().Value("service.instance.id"); ok && serviceInstanceID.AsString() != "" {
		return &opAMPIdentity{instanceUID: instanceUID}, nil
	}

	resourceAttributes := os.Getenv(otelResourceAttributesEnv)
	if resourceAttributes != "" {
		resourceAttributes += ","
	}
	resourceAttributes += "service.instance.id=" + hex.EncodeToString(instanceUID[:])
	if err := os.Setenv(otelResourceAttributesEnv, resourceAttributes); err != nil {
		return nil, fmt.Errorf("set service instance ID: %w", err)
	}

	return &opAMPIdentity{instanceUID: instanceUID}, nil
}

func startOpAMPClient(ctx context.Context, identity *opAMPIdentity) (client.OpAMPClient, error) {
	endpoint := os.Getenv(opAMPServerEndpointEnv)
	if endpoint == "" || identity == nil {
		return nil, nil
	}

	res, err := resource.New(ctx,
		resource.WithFromEnv(),
		resource.WithTelemetrySDK(),
		resource.WithHost(),
		resource.WithContainer(),
	)
	if err != nil {
		logger.Warn("Built partial resource for OpAMP", slog.Any("error", err))
	}
	if res == nil {
		res = resource.Empty()
	}

	var identifying, nonIdentifying []*protobufs.KeyValue
	for _, attr := range res.Attributes() {
		kv := &protobufs.KeyValue{
			Key: string(attr.Key),
			Value: &protobufs.AnyValue{
				Value: &protobufs.AnyValue_StringValue{StringValue: attr.Value.String()},
			},
		}
		switch string(attr.Key) {
		case "service.name", "service.instance.id", "service.namespace":
			identifying = append(identifying, kv)
		default:
			nonIdentifying = append(nonIdentifying, kv)
		}
	}

	opAMPClient := client.NewWebSocket(opAMPLogger{logger: logger})

	err = opAMPClient.SetAgentDescription(&protobufs.AgentDescription{
		IdentifyingAttributes:    identifying,
		NonIdentifyingAttributes: nonIdentifying,
	})
	if err != nil {
		return nil, fmt.Errorf("set agent description: %w", err)
	}

	if err := opAMPClient.SetHealth(&protobufs.ComponentHealth{
		Healthy:           true,
		StartTimeUnixNano: uint64(time.Now().UnixNano()),
	}); err != nil {
		return nil, fmt.Errorf("set health: %w", err)
	}

	capabilities := protobufs.AgentCapabilities_AgentCapabilities_ReportsHealth
	if err := opAMPClient.SetCapabilities(&capabilities); err != nil {
		return nil, fmt.Errorf("set capabilities: %w", err)
	}

	startSettings := types.StartSettings{
		OpAMPServerURL: endpoint,
		InstanceUid:    identity.instanceUID,
	}

	skipTLSCertificateVerificationEnv := os.Getenv(opAMPServerTLSInsecureSkipVerifyEnv)
	skipTLSCertificateVerification, err := strconv.ParseBool(skipTLSCertificateVerificationEnv)
	if err != nil && skipTLSCertificateVerificationEnv != "" {
		return nil, fmt.Errorf("parse %s: %w", opAMPServerTLSInsecureSkipVerifyEnv, err)
	}
	if skipTLSCertificateVerification {
		// The demo's OpAMP server uses a self-signed certificate for wss://.
		startSettings.TLSConfig = &tls.Config{InsecureSkipVerify: true}
	}

	err = opAMPClient.Start(ctx, startSettings)
	if err != nil {
		return nil, fmt.Errorf("start OpAMP client: %w", err)
	}

	return opAMPClient, nil
}
