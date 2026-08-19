// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
package main

import (
	"context"
	"os"
	"strings"
	"testing"

	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/sdk/resource"
)

func TestPrepareOpAmpIdentityDisabled(t *testing.T) {
	t.Setenv(opampServerEndpointEnv, "")
	t.Setenv(otelResourceAttributesEnv, "service.namespace=opentelemetry-demo")

	identity, err := prepareOpAmpIdentity()
	if err != nil {
		t.Fatalf("prepareOpAmpIdentity() error = %v", err)
	}
	if identity != nil {
		t.Fatal("prepareOpAmpIdentity() returned an identity without an endpoint")
	}
	if got := strings.Contains(os.Getenv(otelResourceAttributesEnv), "service.instance.id="); got {
		t.Fatal("prepareOpAmpIdentity() modified resource attributes while disabled")
	}
}

func TestPrepareOpAmpIdentitySharedWithResource(t *testing.T) {
	t.Setenv(opampServerEndpointEnv, "wss://localhost:4320/v1/opamp")
	t.Setenv(otelResourceAttributesEnv, "service.namespace=opentelemetry-demo")

	identity, err := prepareOpAmpIdentity()
	if err != nil {
		t.Fatalf("prepareOpAmpIdentity() error = %v", err)
	}
	if identity == nil {
		t.Fatal("prepareOpAmpIdentity() returned nil")
	}

	want := "service.instance.id=" + identity.serviceInstanceID
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
	if value.AsString() != identity.serviceInstanceID {
		t.Fatalf("service.instance.id = %q, want %q", value.AsString(), identity.serviceInstanceID)
	}
}
