// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
package main

import (
	"context"
	"encoding/hex"
	"os"
	"strings"
	"testing"

	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/sdk/resource"
)

func TestPrepareOpAMPIdentityDisabled(t *testing.T) {
	t.Setenv(opAMPServerEndpointEnv, "")
	t.Setenv(otelResourceAttributesEnv, "service.namespace=opentelemetry-demo")

	identity, err := prepareOpAMPIdentity()
	if err != nil {
		t.Fatalf("prepareOpAMPIdentity() error = %v", err)
	}
	if identity != nil {
		t.Fatal("prepareOpAMPIdentity() returned an identity without an endpoint")
	}
	if got := strings.Contains(os.Getenv(otelResourceAttributesEnv), "service.instance.id="); got {
		t.Fatal("prepareOpAMPIdentity() modified resource attributes while disabled")
	}
}

func TestPrepareOpAMPIdentitySharedWithResource(t *testing.T) {
	t.Setenv(opAMPServerEndpointEnv, "wss://localhost:4320/v1/opamp")
	t.Setenv(otelResourceAttributesEnv, "service.namespace=opentelemetry-demo")

	identity, err := prepareOpAMPIdentity()
	if err != nil {
		t.Fatalf("prepareOpAMPIdentity() error = %v", err)
	}
	if identity == nil {
		t.Fatal("prepareOpAMPIdentity() returned nil")
	}

	wantID := hex.EncodeToString(identity.instanceUID[:])
	want := "service.instance.id=" + wantID
	if got := os.Getenv(otelResourceAttributesEnv); !strings.Contains(got, want) {
		t.Fatalf("%s = %q, want it to contain %q", otelResourceAttributesEnv, got, want)
	}

	res, err := resource.New(context.Background(), resource.WithFromEnv())
	if err != nil {
		t.Fatalf("resource.New() error = %v", err)
	}
	value, ok := res.Set().Value(attribute.Key("service.instance.id"))
	if !ok {
		t.Fatal("service.instance.id not found in resource")
	}
	if value.AsString() != wantID {
		t.Fatalf("service.instance.id = %q, want %q", value.AsString(), wantID)
	}
}

func TestPrepareOpAMPIdentityPreservesConfiguredServiceInstanceID(t *testing.T) {
	t.Setenv(opAMPServerEndpointEnv, "wss://localhost:4320/v1/opamp")
	t.Setenv(otelResourceAttributesEnv, "service.namespace=opentelemetry-demo,service.instance.id=configured-id")

	identity, err := prepareOpAMPIdentity()
	if err != nil {
		t.Fatalf("prepareOpAMPIdentity() error = %v", err)
	}
	if identity == nil {
		t.Fatal("prepareOpAMPIdentity() returned nil")
	}

	if got := os.Getenv(otelResourceAttributesEnv); got != "service.namespace=opentelemetry-demo,service.instance.id=configured-id" {
		t.Fatalf("%s = %q, want configured service.instance.id preserved", otelResourceAttributesEnv, got)
	}

	res, err := resource.New(context.Background(), resource.WithFromEnv())
	if err != nil {
		t.Fatalf("resource.New() error = %v", err)
	}
	value, ok := res.Set().Value(attribute.Key("service.instance.id"))
	if !ok {
		t.Fatal("service.instance.id not found in resource")
	}
	if value.AsString() != "configured-id" {
		t.Fatalf("service.instance.id = %q, want %q", value.AsString(), "configured-id")
	}
}
