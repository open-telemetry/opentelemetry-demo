// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
package main

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"strings"
	"testing"
	"time"

	pb "github.com/open-telemetry/opentelemetry-demo/src/checkout/genproto/oteldemo"
)

type roundTripperFunc func(*http.Request) (*http.Response, error)

func (fn roundTripperFunc) RoundTrip(req *http.Request) (*http.Response, error) {
	return fn(req)
}

func TestSendOrderConfirmationHasBoundedTimeout(t *testing.T) {
	client := &http.Client{
		Transport: roundTripperFunc(func(req *http.Request) (*http.Response, error) {
			deadline, ok := req.Context().Deadline()
			if !ok {
				return nil, fmt.Errorf("email request context has no deadline")
			}

			remaining := time.Until(deadline)
			if remaining <= 0 || remaining > time.Second {
				return nil, fmt.Errorf("email request timeout = %v, want at most %v", remaining, time.Second)
			}

			return &http.Response{
				StatusCode: http.StatusOK,
				Body:       io.NopCloser(strings.NewReader("")),
				Header:     make(http.Header),
				Request:    req,
			}, nil
		}),
	}
	cs := &checkout{
		emailSvcAddr: "http://email.test",
		httpClient:   client,
	}

	err := cs.sendOrderConfirmation(context.Background(), "test@example.com", &pb.OrderResult{})
	if err != nil {
		t.Fatalf("sendOrderConfirmation() error = %v", err)
	}
}
