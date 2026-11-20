// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
package main

import (
	"context"
	"testing"
	"time"

	"github.com/open-feature/go-sdk/openfeature"
	"github.com/open-feature/go-sdk/openfeature/memprovider"
	pb "github.com/opentelemetry/opentelemetry-demo/src/product-catalog/genproto/oteldemo"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

func TestGetProductWithProductCatalogFailureFlag(t *testing.T) {
	if err := openfeature.SetProviderAndWait(memprovider.NewInMemoryProvider(map[string]memprovider.InMemoryFlag{
		"productCatalogFailure": {
			State:          memprovider.Enabled,
			DefaultVariant: "on",
			Variants:       map[string]any{"on": true, "off": false},
		},
	})); err != nil {
		t.Fatalf("SetProviderAndWait() error = %v", err)
	}
	t.Cleanup(func() {
		_ = openfeature.SetProviderAndWait(memprovider.NewInMemoryProvider(map[string]memprovider.InMemoryFlag{}))
	})

	p := &productCatalog{}
	_, err := p.GetProduct(context.Background(), &pb.GetProductRequest{Id: "OLJCESPC7Z"})
	if err == nil {
		t.Fatal("GetProduct() returned no error with productCatalogFailure enabled")
	}

	st, ok := status.FromError(err)
	if !ok {
		t.Fatalf("GetProduct() error is not a gRPC status: %v", err)
	}
	if st.Code() != codes.Internal {
		t.Errorf("GetProduct() code = %v, want %v", st.Code(), codes.Internal)
	}
	want := `failed to query product: pq: could not read block in file "base/16384/24576": Input/output error`
	if st.Message() != want {
		t.Errorf("GetProduct() message = %q, want %q", st.Message(), want)
	}
}

func TestIsSlowQuery(t *testing.T) {
	tests := []struct {
		name    string
		elapsed time.Duration
		want    bool
	}{
		{name: "above threshold", elapsed: 2 * time.Second, want: true},
		{name: "below threshold", elapsed: 500 * time.Millisecond, want: false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := isSlowQuery(tt.elapsed); got != tt.want {
				t.Errorf("isSlowQuery(%v) = %v, want %v", tt.elapsed, got, tt.want)
			}
		})
	}
}
