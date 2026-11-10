// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"math"
	"math/rand"
	"net"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"sync"
	"syscall"
	"time"

	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/log/global"
	semconv "go.opentelemetry.io/otel/semconv/v1.24.0"
	"go.opentelemetry.io/otel/trace"

	"github.com/IBM/sarama"
	"github.com/google/uuid"
	otelhooks "github.com/open-feature/go-sdk-contrib/hooks/open-telemetry/pkg"
	flagd "github.com/open-feature/go-sdk-contrib/providers/flagd/pkg"
	"github.com/open-feature/go-sdk/openfeature"

	"go.opentelemetry.io/contrib/bridges/otelslog"
	"go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc"
	"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
	"go.opentelemetry.io/contrib/instrumentation/runtime"
	"go.opentelemetry.io/otel"
	otelcodes "go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/exporters/otlp/otlplog/otlploggrpc"
	"go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/propagation"

	sdklog "go.opentelemetry.io/otel/sdk/log"
	sdkmetric "go.opentelemetry.io/otel/sdk/metric"
	sdkresource "go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/health"
	healthpb "google.golang.org/grpc/health/grpc_health_v1"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/proto"

	pb "github.com/open-telemetry/opentelemetry-demo/src/checkout/genproto/oteldemo"
	"github.com/open-telemetry/opentelemetry-demo/src/checkout/kafka"
	"github.com/open-telemetry/opentelemetry-demo/src/checkout/money"
)

//go:generate go install google.golang.org/protobuf/cmd/protoc-gen-go
//go:generate go install google.golang.org/grpc/cmd/protoc-gen-go-grpc
//go:generate protoc --go_out=./ --go-grpc_out=./ --proto_path=../../pb ../../pb/demo.proto

var logger *slog.Logger
var tracer trace.Tracer
var resource *sdkresource.Resource
var initResourcesOnce sync.Once

func initResource() *sdkresource.Resource {
	initResourcesOnce.Do(func() {
		extraResources, _ := sdkresource.New(
			context.Background(),
			sdkresource.WithOS(),
			sdkresource.WithProcess(),
			sdkresource.WithContainer(),
			sdkresource.WithHost(),
		)
		resource, _ = sdkresource.Merge(
			sdkresource.Default(),
			extraResources,
		)
	})
	return resource
}

func initTracerProvider() *sdktrace.TracerProvider {
	ctx := context.Background()

	exporter, err := otlptracegrpc.New(ctx)
	if err != nil {
		logger.Error(fmt.Sprintf("new otlp trace grpc exporter failed: %v", err))
	}
	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exporter),
		sdktrace.WithResource(initResource()),
	)
	otel.SetTracerProvider(tp)
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(propagation.TraceContext{}, propagation.Baggage{}))
	return tp
}

func initMeterProvider() *sdkmetric.MeterProvider {
	ctx := context.Background()

	exporter, err := otlpmetricgrpc.New(ctx)
	if err != nil {
		logger.Error(fmt.Sprintf("new otlp metric grpc exporter failed: %v", err))
	}

	mp := sdkmetric.NewMeterProvider(
		sdkmetric.WithReader(sdkmetric.NewPeriodicReader(exporter)),
		sdkmetric.WithResource(initResource()),
	)
	otel.SetMeterProvider(mp)
	return mp
}

func initLoggerProvider() *sdklog.LoggerProvider {
	ctx := context.Background()

	logExporter, err := otlploggrpc.New(ctx)
	if err != nil {
		return nil
	}

	loggerProvider := sdklog.NewLoggerProvider(
		sdklog.WithProcessor(sdklog.NewBatchProcessor(logExporter)),
	)
	global.SetLoggerProvider(loggerProvider)

	return loggerProvider
}

type checkout struct {
	productCatalogSvcAddr string
	cartSvcAddr           string
	currencySvcAddr       string
	shippingSvcAddr       string
	emailSvcAddr          string
	paymentSvcAddr        string
	kafkaBrokerSvcAddr    string
	pb.UnimplementedCheckoutServiceServer
	KafkaProducerClient     sarama.AsyncProducer
	shippingSvcClient       pb.ShippingServiceClient
	productCatalogSvcClient pb.ProductCatalogServiceClient
	cartSvcClient           pb.CartServiceClient
	currencySvcClient       pb.CurrencyServiceClient
	emailSvcClient          pb.EmailServiceClient
	paymentSvcClient        pb.PaymentServiceClient
	httpClient              *http.Client
}

func main() {
	var port string
	mustMapEnv(&port, "CHECKOUT_PORT")

	tp := initTracerProvider()
	defer func() {
		if err := tp.Shutdown(context.Background()); err != nil {
			logger.Error(fmt.Sprintf("Error shutting down tracer provider: %v", err))
		}
	}()

	mp := initMeterProvider()
	defer func() {
		if err := mp.Shutdown(context.Background()); err != nil {
			logger.Error(fmt.Sprintf("Error shutting down meter provider: %v", err))
		}
	}()

	lp := initLoggerProvider()
	defer func() {
		if err := lp.Shutdown(context.Background()); err != nil {
			logger.Error(fmt.Sprintf("Error shutting down logger provider: %v", err))
		}
	}()

	// this *must* be called after the logger provider is initialized
	// otherwise the Sarama producer in kafka/producer.go will not be
	// able to log properly
	logger = otelslog.NewLogger("checkout")
	slog.SetDefault(logger)

	err := runtime.Start(runtime.WithMinimumReadMemStatsInterval(time.Second))
	if err != nil {
		logger.Error((err.Error()))
	}

	// WithoutCache: evaluate every flag against flagd live. The default RPC
	// provider caches per-flag and only invalidates on configuration_change
	// events; runtime flag changes (e.g. via flagd-ui) were not being picked
	// up, so checkout kept routing to payment-vB after paymentFailure was set
	// to off. Disabling the cache makes routing honor the current flag value.
	provider, err := flagd.NewProvider(flagd.WithoutCache())
	if err != nil {
		logger.Error(fmt.Sprintf("Error creating flagd provider: %v", err))
	}

	openfeature.SetProvider(provider)
	openfeature.AddHooks(otelhooks.NewTracesHook())

	tracer = tp.Tracer("checkout")

	svc := new(checkout)
	svc.httpClient = &http.Client{
		Transport: otelhttp.NewTransport(http.DefaultTransport,
			otelhttp.WithSpanOptions(trace.WithAttributes(
				attribute.String("peer.service", "shipping"),
			)),
		),
	}

	mustMapEnv(&svc.shippingSvcAddr, "SHIPPING_ADDR")
	c := mustCreateClient(svc.shippingSvcAddr, "shipping")
	svc.shippingSvcClient = pb.NewShippingServiceClient(c)
	defer c.Close()

	mustMapEnv(&svc.productCatalogSvcAddr, "PRODUCT_CATALOG_ADDR")
	c = mustCreateClient(svc.productCatalogSvcAddr, "product-catalog")
	svc.productCatalogSvcClient = pb.NewProductCatalogServiceClient(c)
	defer c.Close()

	mustMapEnv(&svc.cartSvcAddr, "CART_ADDR")
	c = mustCreateClient(svc.cartSvcAddr, "cart")
	svc.cartSvcClient = pb.NewCartServiceClient(c)
	defer c.Close()

	mustMapEnv(&svc.currencySvcAddr, "CURRENCY_ADDR")
	c = mustCreateClient(svc.currencySvcAddr, "currency")
	svc.currencySvcClient = pb.NewCurrencyServiceClient(c)
	defer c.Close()

	mustMapEnv(&svc.emailSvcAddr, "EMAIL_ADDR")
	c = mustCreateClient(svc.emailSvcAddr, "email")
	svc.emailSvcClient = pb.NewEmailServiceClient(c)
	defer c.Close()

	mustMapEnv(&svc.paymentSvcAddr, "PAYMENT_ADDR")
	c = mustCreateClient(svc.paymentSvcAddr, "payment")
	svc.paymentSvcClient = pb.NewPaymentServiceClient(c)
	defer c.Close()

	svc.kafkaBrokerSvcAddr = os.Getenv("KAFKA_ADDR")

	if svc.kafkaBrokerSvcAddr != "" {
		svc.KafkaProducerClient, err = kafka.CreateKafkaProducer([]string{svc.kafkaBrokerSvcAddr}, logger)
		if err != nil {
			logger.Error(err.Error())
		}
	}

	logger.Info(fmt.Sprintf("service config: %+v", svc))

	lis, err := net.Listen("tcp", fmt.Sprintf(":%s", port))
	if err != nil {
		logger.Error(err.Error())
	}

	var srv = grpc.NewServer(
		grpc.StatsHandler(otelgrpc.NewServerHandler()),
	)
	pb.RegisterCheckoutServiceServer(srv, svc)

	healthcheck := health.NewServer()
	healthpb.RegisterHealthServer(srv, healthcheck)
	logger.Info(fmt.Sprintf("starting to listen on tcp: %q", lis.Addr().String()))
	err = srv.Serve(lis)
	logger.Error(err.Error())

	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM, syscall.SIGKILL)
	defer cancel()

	go func() {
		if err := srv.Serve(lis); err != nil {
			logger.Error(err.Error())
		}
	}()

	<-ctx.Done()

	srv.GracefulStop()
	logger.Info("Checkout gRPC server stopped")
}

func mustMapEnv(target *string, envKey string) {
	v := os.Getenv(envKey)
	if v == "" {
		panic(fmt.Sprintf("environment variable %q not set", envKey))
	}
	*target = v
}

func (cs *checkout) Check(ctx context.Context, req *healthpb.HealthCheckRequest) (*healthpb.HealthCheckResponse, error) {
	return &healthpb.HealthCheckResponse{Status: healthpb.HealthCheckResponse_SERVING}, nil
}

func (cs *checkout) Watch(req *healthpb.HealthCheckRequest, ws healthpb.Health_WatchServer) error {
	return status.Errorf(codes.Unimplemented, "health check via Watch not implemented")
}

// Promo codes applied at checkout. SPRING10 is the live customer campaign.
// PROMOTEST100 is an internal test code that was never removed from the
// pricing rules; when it matches, the order total is discounted to zero.
// NONE means the promo engine is disabled and the customer pays full price.
const (
	noPromoCode       = "NONE"
	livePromoCode     = "SPRING10"
	livePromoDiscount = 10 // percent
	testPromoCode     = "PROMOTEST100"
	testPromoDiscount = 100 // percent

	// promoRedemptionRate is the fraction of orders that redeem any promo code
	// while the promo engine is enabled. Most shoppers don't use one, so the
	// majority of orders stay at full price regardless of the flag setting.
	promoRedemptionRate = 0.30
)

// moneyToFloat converts Money to a decimal value rounded to two places. The
// currency service truncates when packing nanos, so raw conversions arrive with
// long fractional tails; rounding keeps reported amounts at cent precision.
func moneyToFloat(m *pb.Money) float64 {
	v := float64(m.GetUnits()) + float64(m.GetNanos())/1_000_000_000
	return math.Round(v*100) / 100
}

// applyPromoDiscount returns a new Money reduced by discountPct percent.
// Integer arithmetic keeps the result exact for whole-percent discounts.
func applyPromoDiscount(m *pb.Money, discountPct int64) *pb.Money {
	if discountPct <= 0 {
		return m
	}
	if discountPct >= 100 {
		return &pb.Money{CurrencyCode: m.GetCurrencyCode()}
	}
	totalNanos := m.GetUnits()*1_000_000_000 + int64(m.GetNanos())
	kept := totalNanos * (100 - discountPct) / 100
	return &pb.Money{
		CurrencyCode: m.GetCurrencyCode(),
		Units:        kept / 1_000_000_000,
		Nanos:        int32(kept % 1_000_000_000),
	}
}

func (cs *checkout) PlaceOrder(ctx context.Context, req *pb.PlaceOrderRequest) (*pb.PlaceOrderResponse, error) {
	span := trace.SpanFromContext(ctx)
	span.SetAttributes(
		attribute.String("app.user.id", req.UserId),
		attribute.String("app.user.currency", req.UserCurrency),
	)
	logger.LogAttrs(
		ctx,
		slog.LevelInfo, "[PlaceOrder]",
		slog.String("user_id", req.UserId),
		slog.String("user_currency", req.UserCurrency),
	)

	var err error
	defer func() {
		if err != nil {
			span.RecordError(err)
		}
	}()

	orderID, err := uuid.NewUUID()
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to generate order uuid")
	}

	logger.InfoContext(ctx, "entering order preparation", slog.String("order_id", orderID.String()))
	prep, err := cs.prepareOrderItemsAndShippingQuoteFromCart(ctx, req.UserId, req.UserCurrency, req.Address)
	if err != nil {
		// Return FailedPrecondition for empty cart (client error), Internal for other errors
		if err.Error() == "cannot place order with empty cart" {
			return nil, status.Errorf(codes.FailedPrecondition, err.Error())
		}
		return nil, status.Errorf(codes.Internal, err.Error())
	}
	span.AddEvent("prepared")
	logger.InfoContext(ctx, "leaving order preparation",
		slog.Int("order_items", len(prep.orderItems)))

	total := &pb.Money{CurrencyCode: req.UserCurrency,
		Units: 0,
		Nanos: 0}
	total = money.Must(money.Sum(total, prep.shippingCostLocalized))
	for _, it := range prep.orderItems {
		multPrice := money.MultiplySlow(it.Cost, uint32(it.GetItem().GetQuantity()))
		total = money.Must(money.Sum(total, multPrice))
	}

	// Resolve the promo code for this order. The promoDiscountBug flag enables the
	// promo engine; while enabled, promoRedemptionRate of orders redeem a code and
	// the flag value decides what share of those redemptions incorrectly match the
	// internal PROMOTEST100 test code instead of the live SPRING10 campaign. With
	// the flag off no promo is applied at all, so the default behaviour of the demo
	// is unchanged. Only the charged amount is affected -- the order items, shipping
	// cost and the confirmation sent back to the customer all keep the full price.
	promoCode := noPromoCode
	discountPct := int64(0)
	if bugRate := cs.getFeatureFlagFloat(ctx, "promoDiscountBug", 0.0); bugRate > 0 && rand.Float64() < promoRedemptionRate {
		if rand.Float64() < bugRate {
			promoCode = testPromoCode
			discountPct = testPromoDiscount
		} else {
			promoCode = livePromoCode
			discountPct = livePromoDiscount
		}
	}
	chargeTotal := applyPromoDiscount(total, discountPct)

	logger.InfoContext(ctx, "order total calculated",
		slog.String("currency", chargeTotal.GetCurrencyCode()),
		slog.Int64("units", chargeTotal.GetUnits()))
	logger.InfoContext(ctx, "promo code resolved", slog.String("promo_code", promoCode))
	logger.InfoContext(ctx, "entering payment service", slog.String("order_id", orderID.String()))
	txID, err := cs.chargeCard(ctx, chargeTotal, req.CreditCard)
	if err != nil {
		logger.InfoContext(ctx, "leaving payment service", slog.String("result", "declined"))
		// Unwind breadcrumbs. Without these the payment error is the last log
		// line in the whole trace, which hands the root cause to the viewer
		// before they have looked at anything. Each line states something that
		// is actually true about the abandoned order, so the trail stays
		// honest while the failure sits in the middle of the stream rather
		// than at the end.
		logger.InfoContext(ctx, "payment declined, unwinding order",
			slog.String("user_id", req.UserId))
		logger.InfoContext(ctx, "no transaction id returned by payment service")
		logger.InfoContext(ctx, "cart left intact for retry",
			slog.String("user_id", req.UserId))
		logger.InfoContext(ctx, "shipping order not placed")
		logger.InfoContext(ctx, "order confirmation email not sent")
		logger.InfoContext(ctx, "order not published to orders topic")
		logger.InfoContext(ctx, "order total not recorded for reporting")
		for _, it := range prep.orderItems {
			logger.InfoContext(ctx, "order item not charged",
				slog.String("product_id", it.GetItem().GetProductId()),
				slog.Int("quantity", int(it.GetItem().GetQuantity())))
		}
		logger.InfoContext(ctx, "promo code not redeemed", slog.String("promo_code", promoCode))
		logger.InfoContext(ctx, "order id released", slog.String("order_id", orderID.String()))
		logger.InfoContext(ctx, "returning INTERNAL to caller")
		logger.InfoContext(ctx, "leaving PlaceOrder",
			slog.String("user_id", req.UserId),
			slog.String("outcome", "abandoned"))
		// Generic 500 to callers. Payment's 401 / API token must not land on
		// this span as grpc.error_message, otel.status_description, or
		// exception.message — that is only in payment logs.
		return nil, status.Error(codes.Internal, "Internal Server Error")
	}

	span.AddEvent("charged",
		trace.WithAttributes(attribute.String("app.payment.transaction.id", txID)))
	logger.LogAttrs(
		ctx,
		slog.LevelInfo, "payment went through",
		slog.String("transaction_id", txID),
	)

	shippingTrackingID, err := cs.shipOrder(ctx, req.Address, prep.cartItems)
	if err != nil {
		return nil, status.Errorf(codes.Unavailable, "shipping error: %+v", err)
	}
	shippingTrackingAttribute := attribute.String("app.shipping.tracking.id", shippingTrackingID)
	span.AddEvent("shipped", trace.WithAttributes(shippingTrackingAttribute))

	_ = cs.emptyUserCart(ctx, req.UserId)

	orderResult := &pb.OrderResult{
		OrderId:            orderID.String(),
		ShippingTrackingId: shippingTrackingID,
		ShippingCost:       prep.shippingCostLocalized,
		ShippingAddress:    req.Address,
		Items:              prep.orderItems,
	}

	// Normalize to USD so revenue can be aggregated across currencies. This runs
	// after the charge so it stays off the payment path. The promo discount is a
	// flat percentage, so converting the pre-discount total once and re-applying
	// the discount avoids a second currency conversion.
	totalUSD := total
	if total.GetCurrencyCode() != "USD" {
		if convertedUSD, cerr := cs.convertCurrency(ctx, total, "USD"); cerr == nil {
			totalUSD = convertedUSD
		} else {
			logger.Warn(fmt.Sprintf("failed to convert order total to USD for reporting: %+v", cerr))
		}
	}
	chargeTotalUSD := applyPromoDiscount(totalUSD, discountPct)

	shippingCostFloat, _ := strconv.ParseFloat(fmt.Sprintf("%d.%02d", prep.shippingCostLocalized.GetUnits(), prep.shippingCostLocalized.GetNanos()/1000000000), 64)
	totalPriceFloat := moneyToFloat(total)
	chargedPriceFloat := moneyToFloat(chargeTotal)
	totalUSDFloat := moneyToFloat(totalUSD)
	chargedUSDFloat := moneyToFloat(chargeTotalUSD)

	span.SetAttributes(
		attribute.String("app.order.id", orderID.String()),
		attribute.Float64("app.shipping.amount", shippingCostFloat),
		attribute.Float64("app.order.amount", totalPriceFloat),
		attribute.Int("app.order.items.count", len(prep.orderItems)),
		shippingTrackingAttribute,
	)
	
	orderLog := map[string]any{
		"message":                      "order placed",
		"app.order.id":                 orderID.String(),
		"app.shipping.amount":          shippingCostFloat,
		"app.order.amount":             totalPriceFloat,
		"app.order.amount.charged":     chargedPriceFloat,
		"app.order.currency":           total.GetCurrencyCode(),
		"app.order.amount.usd":         totalUSDFloat,
		"app.order.amount.charged.usd": chargedUSDFloat,
		"app.promo.code":               promoCode,
		"app.order.discount.pct":       float64(discountPct),
		"app.order.items.count":        len(prep.orderItems),
		"app.shipping.tracking.id":     shippingTrackingID,
	}

	if payload, err := json.Marshal(orderLog); err != nil {
		logger.ErrorContext(ctx, "failed to serialize order log",
			slog.String("error", err.Error()),
			slog.String("app.order.id", orderID.String()),
		)
	} else {
		logger.InfoContext(ctx, string(payload))
	}

	if err := cs.sendOrderConfirmation(ctx, req.Email, orderResult); err != nil {
		logger.Warn(fmt.Sprintf("failed to send order confirmation: %+v", err))
	} else {
		logger.Info("order confirmation email sent")
	}

	// send to kafka only if kafka broker address is set
	if cs.kafkaBrokerSvcAddr != "" {
		logger.Info("sending to postProcessor")
		cs.sendToPostProcessor(ctx, orderResult)
	}

	resp := &pb.PlaceOrderResponse{Order: orderResult}
	return resp, nil
}

type orderPrep struct {
	orderItems            []*pb.OrderItem
	cartItems             []*pb.CartItem
	shippingCostLocalized *pb.Money
}

func (cs *checkout) prepareOrderItemsAndShippingQuoteFromCart(ctx context.Context, userID, userCurrency string, address *pb.Address) (orderPrep, error) {

	ctx, span := tracer.Start(ctx, "prepareOrderItemsAndShippingQuoteFromCart")
	defer span.End()

	var out orderPrep

	logger.InfoContext(ctx, "entering cart service", slog.String("user_id", userID))
	cartItems, err := cs.getUserCart(ctx, userID)
	if err != nil {
		return out, fmt.Errorf("cart failure: %+v", err)
	}
	logger.InfoContext(ctx, "leaving cart service", slog.Int("items", len(cartItems)))

	// Validate cart is not empty before proceeding
	if len(cartItems) == 0 {
		return out, fmt.Errorf("cannot place order with empty cart")
	}

	logger.InfoContext(ctx, "entering product catalog service")
	orderItems, err := cs.prepOrderItems(ctx, cartItems, userCurrency)
	if err != nil {
		return out, fmt.Errorf("failed to prepare order: %+v", err)
	}
	logger.InfoContext(ctx, "leaving product catalog service", slog.Int("order_items", len(orderItems)))

	logger.InfoContext(ctx, "entering shipping service")
	shippingUSD, err := cs.quoteShipping(ctx, address, cartItems)
	if err != nil {
		return out, fmt.Errorf("shipping quote failure: %+v", err)
	}
	logger.InfoContext(ctx, "leaving shipping service")

	logger.InfoContext(ctx, "entering currency service", slog.String("target_currency", userCurrency))
	shippingPrice, err := cs.convertCurrency(ctx, shippingUSD, userCurrency)
	if err != nil {
		return out, fmt.Errorf("failed to convert shipping cost to currency: %+v", err)
	}
	logger.InfoContext(ctx, "leaving currency service")

	out.shippingCostLocalized = shippingPrice
	out.cartItems = cartItems
	out.orderItems = orderItems

	var totalCart int32
	for _, ci := range cartItems {
		totalCart += ci.Quantity
	}
	shippingCostFloat, _ := strconv.ParseFloat(fmt.Sprintf("%d.%02d", shippingPrice.GetUnits(), shippingPrice.GetNanos()/1000000000), 64)

	span.SetAttributes(
		attribute.Float64("app.shipping.amount", shippingCostFloat),
		attribute.Int("app.cart.items.count", int(totalCart)),
		attribute.Int("app.order.items.count", len(orderItems)),
	)
	return out, nil
}

func mustCreateClient(svcAddr string, peerService string) *grpc.ClientConn {
	c, err := grpc.NewClient(svcAddr,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithStatsHandler(otelgrpc.NewClientHandler(
			otelgrpc.WithSpanAttributes(
				attribute.String("peer.service", peerService),
			),
		)),
	)
	if err != nil {
		logger.Error(fmt.Sprintf("could not connect to %s service, err: %+v", svcAddr, err))
	}

	return c
}

func (cs *checkout) quoteShipping(ctx context.Context, address *pb.Address, items []*pb.CartItem) (*pb.Money, error) {
	// Ensure items is an empty array instead of null when cart is empty
	if items == nil {
		items = []*pb.CartItem{}
	}

	quotePayload, err := json.Marshal(map[string]interface{}{
		"address": address,
		"items":   items,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to marshal ship order request: %+v", err)
	}

	req, err := http.NewRequestWithContext(ctx, "POST", cs.shippingSvcAddr+"/get-quote", bytes.NewBuffer(quotePayload))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %+v", err)
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := cs.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed POST to shipping service: %+v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("failed POST to shipping service: expected 200, got %d", resp.StatusCode)
	}

	shippingQuoteBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read shipping quote response: %+v", err)
	}

	var quoteResp struct {
		CostUsd *pb.Money `json:"cost_usd"`
	}
	if err := json.Unmarshal(shippingQuoteBytes, &quoteResp); err != nil {
		return nil, fmt.Errorf("failed to unmarshal shipping quote: %+v", err)
	}
	if quoteResp.CostUsd == nil {
		return nil, fmt.Errorf("shipping quote missing cost_usd field")
	}

	return quoteResp.CostUsd, nil
}

func (cs *checkout) getUserCart(ctx context.Context, userID string) ([]*pb.CartItem, error) {
	cart, err := cs.cartSvcClient.GetCart(ctx, &pb.GetCartRequest{UserId: userID})
	if err != nil {
		return nil, fmt.Errorf("failed to get user cart during checkout: %+v", err)
	}
	return cart.GetItems(), nil
}

func (cs *checkout) emptyUserCart(ctx context.Context, userID string) error {
	if _, err := cs.cartSvcClient.EmptyCart(ctx, &pb.EmptyCartRequest{UserId: userID}); err != nil {
		return fmt.Errorf("failed to empty user cart during checkout: %+v", err)
	}
	return nil
}

func (cs *checkout) prepOrderItems(ctx context.Context, items []*pb.CartItem, userCurrency string) ([]*pb.OrderItem, error) {
	out := make([]*pb.OrderItem, len(items))

	for i, item := range items {
		product, err := cs.productCatalogSvcClient.GetProduct(ctx, &pb.GetProductRequest{Id: item.GetProductId()})
		if err != nil {
			return nil, fmt.Errorf("failed to get product #%q", item.GetProductId())
		}
		price, err := cs.convertCurrency(ctx, product.GetPriceUsd(), userCurrency)
		if err != nil {
			return nil, fmt.Errorf("failed to convert price of %q to %s", item.GetProductId(), userCurrency)
		}
		out[i] = &pb.OrderItem{
			Item: item,
			Cost: price}
	}
	return out, nil
}

func (cs *checkout) convertCurrency(ctx context.Context, from *pb.Money, toCurrency string) (*pb.Money, error) {
	result, err := cs.currencySvcClient.Convert(ctx, &pb.CurrencyConversionRequest{
		From:   from,
		ToCode: toCurrency})
	if err != nil {
		return nil, fmt.Errorf("failed to convert currency: %+v", err)
	}
	return result, err
}

// chargeCard routes payment requests to payment-va or payment-vb service.
//
// Payment Routing Behavior:
//   - If x-payment-path header is present (rumBlueGreen flag ON in frontend):
//     Uses the header value ('payment-a' -> payment-va, 'payment-b' -> payment-vb)
//     This enables RUM to track payment path from session start to checkout.
//   - If header is absent (rumBlueGreen flag OFF or missing):
//     Uses paymentFailure flag probability to randomly route requests.
//     e.g., paymentFailure=0.5 means 50% go to payment-vb.
//     Default (paymentFailure=0) routes 100% to payment-va.
func (cs *checkout) chargeCard(ctx context.Context, amount *pb.Money, paymentInfo *pb.CreditCardInfo) (string, error) {
	paymentService := cs.paymentSvcClient

	// Check for intentional failure mode (uses existing paymentUnreachable flag)
	if cs.isFeatureFlagEnabled(ctx, "paymentUnreachable") {
		badAddress := "badAddress:50051"
		c := mustCreateClient(badAddress, "payment")
		paymentService = pb.NewPaymentServiceClient(c)
	} else {
		var paymentAddr string

		// Check for frontend-determined payment path (from RUM blue/green feature)
		// This header is set when rumBlueGreen flag is enabled in frontend
		paymentPath := ""
		if md, ok := metadata.FromIncomingContext(ctx); ok {
			if values := md.Get("x-payment-path"); len(values) > 0 {
				paymentPath = values[0]
			}
		}

		if paymentPath == "payment-b" {
			// Frontend determined: route to version B
			paymentAddr = "payment-vb:8080"
			logger.Info("Using frontend-determined payment path: B (from x-payment-path header)")
		} else if paymentPath == "payment-a" {
			// Frontend determined: route to version A
			paymentAddr = "payment-va:8080"
			logger.Info("Using frontend-determined payment path: A (from x-payment-path header)")
		} else {
			// Fallback: existing flag-based decision (rumBlueGreen not enabled or header missing)
			// Use paymentFailure flag to route between payment version A and B
			// paymentFailure=0   → 100% to version A
			// paymentFailure=0.5 → 50% to A, 50% to B
			// paymentFailure=1   → 100% to version B
			paymentFailureProbability := cs.getFeatureFlagFloat(ctx, "paymentFailure", 0.0)

			// Generate random number to determine routing
			shouldRouteToB := rand.Float64() < paymentFailureProbability

			if shouldRouteToB {
				// Route to version B (optimized/faster)
				paymentAddr = "payment-vb:8080"
			} else {
				// Route to version A (stable/conservative)
				paymentAddr = "payment-va:8080"
			}
			logger.Info(fmt.Sprintf("Using backend flag-based payment path decision: %s", paymentAddr))
		}

		// Create client for selected version
		c := mustCreateClient(paymentAddr, "payment")
		defer c.Close()
		paymentService = pb.NewPaymentServiceClient(c)
	}

	paymentResp, err := paymentService.Charge(ctx, &pb.ChargeRequest{
		Amount:     amount,
		CreditCard: paymentInfo})
	if err != nil {
		// Payment already returned gRPC INTERNAL ("Internal Server Error").
		// Do not wrap the RPC error — that used to leak "code = Code(401)"
		// into PlaceOrder / frontend. Re-state the generic message only.
		return "", status.Error(codes.Internal, "Internal Server Error")
	}
	return paymentResp.GetTransactionId(), nil
}

func (cs *checkout) sendOrderConfirmation(ctx context.Context, email string, order *pb.OrderResult) error {
	emailPayload, err := json.Marshal(map[string]interface{}{
		"email": email,
		"order": order,
	})
	if err != nil {
		return fmt.Errorf("failed to marshal order to JSON: %+v", err)
	}

	req, err := http.NewRequestWithContext(ctx, "POST", cs.emailSvcAddr+"/send_order_confirmation", bytes.NewBuffer(emailPayload))
	if err != nil {
		return fmt.Errorf("failed to create request: %+v", err)
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := cs.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed POST to email service: %+v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("failed POST to email service: expected 200, got %d", resp.StatusCode)
	}

	return err
}

func (cs *checkout) shipOrder(ctx context.Context, address *pb.Address, items []*pb.CartItem) (string, error) {
	// Ensure items is an empty array instead of null when cart is empty
	if items == nil {
		items = []*pb.CartItem{}
	}

	shipPayload, err := json.Marshal(map[string]interface{}{
		"address": address,
		"items":   items,
	})
	if err != nil {
		return "", fmt.Errorf("failed to marshal ship order request: %+v", err)
	}

	req, err := http.NewRequestWithContext(ctx, "POST", cs.shippingSvcAddr+"/ship-order", bytes.NewBuffer(shipPayload))
	if err != nil {
		return "", fmt.Errorf("failed to create request: %+v", err)
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := cs.httpClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("failed POST to shipping service: %+v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("failed POST to shipping service: expected 200, got %d", resp.StatusCode)
	}

	trackingRespBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", fmt.Errorf("failed to read ship order response: %+v", err)
	}

	var shipResp struct {
		TrackingID string `json:"tracking_id"`
	}
	if err := json.Unmarshal(trackingRespBytes, &shipResp); err != nil {
		return "", fmt.Errorf("failed to unmarshal ship order response: %+v", err)
	}
	if shipResp.TrackingID == "" {
		return "", fmt.Errorf("ship order response missing tracking_id field")
	}

	return shipResp.TrackingID, nil
}

func (cs *checkout) sendToPostProcessor(ctx context.Context, result *pb.OrderResult) {
	message, err := proto.Marshal(result)
	if err != nil {
		logger.Error(fmt.Sprintf("Failed to marshal message to protobuf: %+v", err))
		return
	}

	msg := sarama.ProducerMessage{
		Topic: kafka.Topic,
		Value: sarama.ByteEncoder(message),
	}

	// Inject tracing info into message
	span := createProducerSpan(ctx, &msg)
	defer span.End()

	// Send message and handle response
	startTime := time.Now()
	select {
	case cs.KafkaProducerClient.Input() <- &msg:
		select {
		case successMsg := <-cs.KafkaProducerClient.Successes():
			span.SetAttributes(
				attribute.Bool("messaging.kafka.producer.success", true),
				attribute.Int("messaging.kafka.producer.duration_ms", int(time.Since(startTime).Milliseconds())),
				attribute.KeyValue(semconv.MessagingKafkaMessageOffset(int(successMsg.Offset))),
			)
			logger.Info(fmt.Sprintf("Successful to write message. offset: %v, duration: %v", successMsg.Offset, time.Since(startTime)))
		case errMsg := <-cs.KafkaProducerClient.Errors():
			span.SetAttributes(
				attribute.Bool("messaging.kafka.producer.success", false),
				attribute.Int("messaging.kafka.producer.duration_ms", int(time.Since(startTime).Milliseconds())),
			)
			span.SetStatus(otelcodes.Error, errMsg.Err.Error())
			logger.Error(fmt.Sprintf("Failed to write message: %v", errMsg.Err))
		case <-ctx.Done():
			span.SetAttributes(
				attribute.Bool("messaging.kafka.producer.success", false),
				attribute.Int("messaging.kafka.producer.duration_ms", int(time.Since(startTime).Milliseconds())),
			)
			span.SetStatus(otelcodes.Error, "Context cancelled: "+ctx.Err().Error())
			logger.Warn(fmt.Sprintf("Context canceled before success message received: %v", ctx.Err()))
		}
	case <-ctx.Done():
		span.SetAttributes(
			attribute.Bool("messaging.kafka.producer.success", false),
			attribute.Int("messaging.kafka.producer.duration_ms", int(time.Since(startTime).Milliseconds())),
		)
		span.SetStatus(otelcodes.Error, "Failed to send: "+ctx.Err().Error())
		logger.Error(fmt.Sprintf("Failed to send message to Kafka within context deadline: %v", ctx.Err()))
		return
	}

	ffValue := cs.getIntFeatureFlag(ctx, "kafkaQueueProblems")
	if ffValue > 0 {
		logger.Info("Warning: FeatureFlag 'kafkaQueueProblems' is activated, overloading queue now.")
		for i := 0; i < ffValue; i++ {
			go func(i int) {
				cs.KafkaProducerClient.Input() <- &msg
				_ = <-cs.KafkaProducerClient.Successes()
			}(i)
		}
		logger.Info(fmt.Sprintf("Done with #%d messages for overload simulation.", ffValue))
	}
}

func createProducerSpan(ctx context.Context, msg *sarama.ProducerMessage) trace.Span {
	spanContext, span := tracer.Start(
		ctx,
		fmt.Sprintf("%s publish", msg.Topic),
		trace.WithSpanKind(trace.SpanKindProducer),
		trace.WithAttributes(
			semconv.PeerService("kafka"),
			semconv.NetworkTransportTCP,
			semconv.MessagingSystemKafka,
			semconv.MessagingDestinationName(msg.Topic),
			semconv.MessagingOperationPublish,
			semconv.MessagingKafkaDestinationPartition(int(msg.Partition)),
		),
	)

	carrier := propagation.MapCarrier{}
	propagator := otel.GetTextMapPropagator()
	propagator.Inject(spanContext, carrier)

	for key, value := range carrier {
		msg.Headers = append(msg.Headers, sarama.RecordHeader{Key: []byte(key), Value: []byte(value)})
	}

	return span
}

func (cs *checkout) isFeatureFlagEnabled(ctx context.Context, featureFlagName string) bool {
	client := openfeature.NewClient("checkout")

	// Default value is set to false, but you could also make this a parameter.
	featureEnabled, _ := client.BooleanValue(
		ctx,
		featureFlagName,
		false,
		openfeature.EvaluationContext{},
	)

	return featureEnabled
}

func (cs *checkout) getIntFeatureFlag(ctx context.Context, featureFlagName string) int {
	client := openfeature.NewClient("checkout")

	// Default value is set to 0, but you could also make this a parameter.
	featureFlagValue, _ := client.IntValue(
		ctx,
		featureFlagName,
		0,
		openfeature.EvaluationContext{},
	)

	return int(featureFlagValue)
}

func (cs *checkout) getFeatureFlagString(ctx context.Context, featureFlagName string, defaultValue string) string {
	client := openfeature.NewClient("checkout")

	// Get string value from feature flag
	featureFlagValue, _ := client.StringValue(
		ctx,
		featureFlagName,
		defaultValue,
		openfeature.EvaluationContext{},
	)

	return featureFlagValue
}

func (cs *checkout) getFeatureFlagFloat(ctx context.Context, featureFlagName string, defaultValue float64) float64 {
	client := openfeature.NewClient("checkout")

	// Get float value from feature flag
	featureFlagValue, _ := client.FloatValue(
		ctx,
		featureFlagName,
		defaultValue,
		openfeature.EvaluationContext{},
	)

	return featureFlagValue
}
