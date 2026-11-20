// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"log/slog"
	"net/http"
	"strings"
	"testing"

	"go.opentelemetry.io/otel"
	"google.golang.org/grpc"

	pb "github.com/open-telemetry/opentelemetry-demo/src/checkout/genproto/oteldemo"
)

type fakeCart struct{ pb.CartServiceClient }

func (fakeCart) GetCart(_ context.Context, _ *pb.GetCartRequest, _ ...grpc.CallOption) (*pb.Cart, error) {
	return &pb.Cart{Items: []*pb.CartItem{{ProductId: "p1", Quantity: 1}}}, nil
}

type fakeCatalog struct{ pb.ProductCatalogServiceClient }

func (fakeCatalog) GetProduct(_ context.Context, _ *pb.GetProductRequest, _ ...grpc.CallOption) (*pb.Product, error) {
	return &pb.Product{PriceUsd: &pb.Money{CurrencyCode: "USD", Units: 1}}, nil
}

type fakeCurrency struct{ pb.CurrencyServiceClient }

func (fakeCurrency) Convert(_ context.Context, r *pb.CurrencyConversionRequest, _ ...grpc.CallOption) (*pb.Money, error) {
	return r.GetFrom(), nil
}

type fakePayment struct{ pb.PaymentServiceClient }

func (fakePayment) Charge(_ context.Context, _ *pb.ChargeRequest, _ ...grpc.CallOption) (*pb.ChargeResponse, error) {
	return nil, errors.New("card declined")
}

type fakePaymentOK struct{ pb.PaymentServiceClient }

func (fakePaymentOK) Charge(_ context.Context, _ *pb.ChargeRequest, _ ...grpc.CallOption) (*pb.ChargeResponse, error) {
	return &pb.ChargeResponse{TransactionId: "tx-1"}, nil
}

func (fakeCart) EmptyCart(_ context.Context, _ *pb.EmptyCartRequest, _ ...grpc.CallOption) (*pb.Empty, error) {
	return &pb.Empty{}, nil
}

func TestPlaceOrderSuccessLogsOrderSummary(t *testing.T) {
	var buf bytes.Buffer
	prevTracer := tracer
	tracer = otel.Tracer("checkout-test")
	defer func() { tracer = prevTracer }()
	prev := logger
	logger = slog.New(slog.NewJSONHandler(&buf, nil))
	defer func() { logger = prev }()

	client := &http.Client{
		Transport: roundTripperFunc(func(req *http.Request) (*http.Response, error) {
			body, _ := json.Marshal(map[string]any{
				"cost_usd":    map[string]any{"currency_code": "USD", "units": 1},
				"tracking_id": "ship-1",
			})
			return &http.Response{
				StatusCode: http.StatusOK,
				Body:       io.NopCloser(strings.NewReader(string(body))),
				Header:     make(http.Header),
				Request:    req,
			}, nil
		}),
	}
	cs := &checkout{
		shippingSvcAddr:         "http://shipping.test",
		httpClient:              client,
		cartSvcClient:           fakeCart{},
		productCatalogSvcClient: fakeCatalog{},
		currencySvcClient:       fakeCurrency{},
		paymentSvcClient:        fakePaymentOK{},
	}
	if _, err := cs.PlaceOrder(context.Background(), &pb.PlaceOrderRequest{UserId: "user-1", UserCurrency: "USD"}); err != nil {
		t.Fatalf("PlaceOrder() error = %v, want nil", err)
	}
	var found map[string]any
	for _, line := range strings.Split(strings.TrimSpace(buf.String()), "\n") {
		var rec map[string]any
		if json.Unmarshal([]byte(line), &rec) != nil {
			continue
		}
		if msg, _ := rec["msg"].(string); strings.HasPrefix(msg, "Order placed: ") {
			found = rec
		}
	}
	if found == nil {
		t.Fatalf("no 'Order placed' log in output: %s", buf.String())
	}
	if found["user.id"] != "user-1" {
		t.Errorf("user.id = %v, want user-1", found["user.id"])
	}
	if id, _ := found["demo.order.id"].(string); id == "" {
		t.Errorf("demo.order.id missing from log: %v", found)
	}
}

func TestPlaceOrderChargeFailureLogsUserIDAndError(t *testing.T) {
	var buf bytes.Buffer
	prevTracer := tracer
	tracer = otel.Tracer("checkout-test")
	defer func() { tracer = prevTracer }()
	prev := logger
	logger = slog.New(slog.NewJSONHandler(&buf, nil))
	defer func() { logger = prev }()

	client := &http.Client{
		Transport: roundTripperFunc(func(req *http.Request) (*http.Response, error) {
			body, _ := json.Marshal(map[string]any{"cost_usd": map[string]any{"currency_code": "USD", "units": 1}})
			return &http.Response{
				StatusCode: http.StatusOK,
				Body:       io.NopCloser(strings.NewReader(string(body))),
				Header:     make(http.Header),
				Request:    req,
			}, nil
		}),
	}
	cs := &checkout{
		shippingSvcAddr:         "http://shipping.test",
		httpClient:              client,
		cartSvcClient:           fakeCart{},
		productCatalogSvcClient: fakeCatalog{},
		currencySvcClient:       fakeCurrency{},
		paymentSvcClient:        fakePayment{},
	}

	_, err := cs.PlaceOrder(context.Background(), &pb.PlaceOrderRequest{UserId: "user-1", UserCurrency: "USD"})
	if err == nil {
		t.Fatal("PlaceOrder() error = nil, want charge failure")
	}

	var found map[string]any
	for _, line := range strings.Split(strings.TrimSpace(buf.String()), "\n") {
		var rec map[string]any
		if json.Unmarshal([]byte(line), &rec) != nil {
			continue
		}
		if msg, _ := rec["msg"].(string); strings.HasPrefix(msg, "failed to charge card: ") {
			found = rec
		}
	}
	if found == nil {
		t.Fatalf("no 'failed to charge card' log in output: %s", buf.String())
	}
	if found["user.id"] != "user-1" {
		t.Errorf("user.id = %v, want user-1", found["user.id"])
	}
	if _, ok := found["error"]; !ok {
		t.Errorf("error attribute missing from log: %v", found)
	}
}
