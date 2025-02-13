// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
package main

//go:generate go install google.golang.org/protobuf/cmd/protoc-gen-go
//go:generate go install google.golang.org/grpc/cmd/protoc-gen-go-grpc
//go:generate protoc --go_out=./ --go-grpc_out=./ --proto_path=../../pb ../../pb/demo.proto

import (
	"context"
	"errors"
	"fmt"
	"math/rand/v2"
	"net"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"github.com/sirupsen/logrus"

	"go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc"
	"go.opentelemetry.io/contrib/instrumentation/runtime"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	otelcodes "go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/propagation"
	sdkmetric "go.opentelemetry.io/otel/sdk/metric"
	sdkresource "go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	"go.opentelemetry.io/otel/trace"

	"gorm.io/driver/sqlite"
	"gorm.io/gorm"

	"github.com/golang-migrate/migrate/v4"
	_ "github.com/golang-migrate/migrate/v4/database/sqlite"
	_ "github.com/golang-migrate/migrate/v4/source/file"
	_ "github.com/mattn/go-sqlite3"
	otelhooks "github.com/open-feature/go-sdk-contrib/hooks/open-telemetry/pkg"
	flagd "github.com/open-feature/go-sdk-contrib/providers/flagd/pkg"
	"github.com/open-feature/go-sdk/openfeature"
	pb "github.com/opentelemetry/opentelemetry-demo/src/product-catalog/genproto/oteldemo"
	models "github.com/opentelemetry/opentelemetry-demo/src/product-catalog/models"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	healthpb "google.golang.org/grpc/health/grpc_health_v1"
	"google.golang.org/grpc/reflection"
	"google.golang.org/grpc/status"
	"gorm.io/plugin/opentelemetry/tracing"
)

var (
	log               *logrus.Logger
	db                *gorm.DB
	catalog           []*pb.Product
	resource          *sdkresource.Resource
	initResourcesOnce sync.Once
)

type ctxKey string

const slowLoadKey ctxKey = "slowLoad"

func init() {
	log = logrus.New()
}

func init() {
	m, err := migrate.New(
		"file://migrations/",
		"sqlite://products/products.db")
	if err != nil {
		log.Errorf("Error creating migration instance: %v", err)
	}

	defer m.Close()

	err = m.Up()

	if err != nil {
		log.Errorf("Error running database migrations: %v", err)
	} else {
		log.Info("Migrations run successfully")
	}
}

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
		log.Fatalf("OTLP Trace gRPC Creation: %v", err)
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
		log.Fatalf("new otlp metric grpc exporter failed: %v", err)
	}

	mp := sdkmetric.NewMeterProvider(
		sdkmetric.WithReader(sdkmetric.NewPeriodicReader(exporter)),
		sdkmetric.WithResource(initResource()),
	)
	otel.SetMeterProvider(mp)
	return mp
}

func connectDB() *gorm.DB {
	db, err := gorm.Open(sqlite.Open("products/products.db"), &gorm.Config{})
	if err != nil {
		log.Fatalf("Error connecting to the database: %v", err)
		panic(err)
	}

	if err := db.Use(tracing.NewPlugin()); err != nil {
		log.Fatalf("Error instrumenting the database: %v", err)
		panic(err)
	}

	var products []models.Product
	db.Preload("ProductPrices").Preload("Categories").Find(&products)
	log.Infof("Found %d products", len(products))

	db.Callback().Query().Before("otel:after:select").Register("slowdown", func(db *gorm.DB) {
		if slowLoad, ok := db.Statement.Context.Value(slowLoadKey).(bool); ok && slowLoad {
			time.Sleep(200 * time.Millisecond)
		}
	})

	return db
}

func main() {
	tp := initTracerProvider()
	defer func() {
		if err := tp.Shutdown(context.Background()); err != nil {
			log.Fatalf("Tracer Provider Shutdown: %v", err)
		}
		log.Println("Shutdown tracer provider")
	}()

	mp := initMeterProvider()
	defer func() {
		if err := mp.Shutdown(context.Background()); err != nil {
			log.Fatalf("Error shutting down meter provider: %v", err)
		}
		log.Println("Shutdown meter provider")
	}()
	openfeature.AddHooks(otelhooks.NewTracesHook())
	err := openfeature.SetProvider(flagd.NewProvider())
	if err != nil {
		log.Fatal(err)
	}

	db = connectDB()

	err = runtime.Start(runtime.WithMinimumReadMemStatsInterval(time.Second))
	if err != nil {
		log.Fatal(err)
	}

	svc := &productCatalog{
		client: openfeature.NewClient("productCatalog"),
	}

	var port string
	mustMapEnv(&port, "PRODUCT_CATALOG_PORT")

	log.Infof("Product Catalog gRPC server started on port: %s", port)

	ln, err := net.Listen("tcp", fmt.Sprintf(":%s", port))
	if err != nil {
		log.Fatalf("TCP Listen: %v", err)
	}

	srv := grpc.NewServer(
		grpc.StatsHandler(otelgrpc.NewServerHandler()),
	)

	reflection.Register(srv)

	pb.RegisterProductCatalogServiceServer(srv, svc)
	healthpb.RegisterHealthServer(srv, svc)

	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM, syscall.SIGKILL)
	defer cancel()

	go func() {
		if err := srv.Serve(ln); err != nil {
			log.Fatalf("Failed to serve gRPC server, err: %v", err)
		}
	}()

	<-ctx.Done()

	srv.GracefulStop()
	log.Println("Product Catalog gRPC server stopped")
}

type productCatalog struct {
	pb.UnimplementedProductCatalogServiceServer
	client *openfeature.Client
}

func mustMapEnv(target *string, key string) {
	value, present := os.LookupEnv(key)
	if !present {
		log.Fatalf("Environment Variable Not Set: %q", key)
	}
	*target = value
}

func (p *productCatalog) Check(ctx context.Context, req *healthpb.HealthCheckRequest) (*healthpb.HealthCheckResponse, error) {
	return &healthpb.HealthCheckResponse{Status: healthpb.HealthCheckResponse_SERVING}, nil
}

func (p *productCatalog) Watch(req *healthpb.HealthCheckRequest, ws healthpb.Health_WatchServer) error {
	return status.Errorf(codes.Unimplemented, "health check via Watch not implemented")
}

func (p *productCatalog) ListProducts(ctx context.Context, req *pb.Empty) (*pb.ListProductsResponse, error) {
	span := trace.SpanFromContext(ctx)

	span.SetAttributes(
		attribute.Int("app.products.count", len(catalog)),
	)

	slowLoadEnabled := p.checkProductSlowLoad(ctx)
	ctx = context.WithValue(ctx, slowLoadKey, slowLoadEnabled)

	var found []models.Product
	if slowLoadEnabled {
		log.Info("Product catalog slow load feature flag enabled")
		if err := db.WithContext(ctx).Preload("Categories").Find(&found).Error; err != nil {
			msg := "Error fetching products from the database"
			span.SetStatus(otelcodes.Error, msg)
			span.AddEvent(msg)
			return nil, status.Error(codes.Internal, msg)
		}

		for idx := range found {
			var prices []models.ProductPrice
			if err := db.WithContext(ctx).Find(&prices, "product_id = ?", found[idx].ID).Error; err != nil {
				msg := fmt.Sprintf("Error fetching product %s price from the database", found[idx].ID)
				span.SetStatus(otelcodes.Error, msg)
				span.AddEvent(msg)
				return nil, status.Error(codes.Internal, msg)
			}
			found[idx].ProductPrices = prices
		}
	} else {
		if err := db.WithContext(ctx).Preload("ProductPrices").Preload("Categories").Find(&found).Error; err != nil {
			msg := "Error fetching products from the database"
			span.SetStatus(otelcodes.Error, msg)
			span.AddEvent(msg)
			return nil, status.Error(codes.Internal, msg)
		}
	}

	var products []*pb.Product
	for idx := range found {
		converted := found[idx].ToProto()
		products = append(products, converted)
	}

	return &pb.ListProductsResponse{Products: products}, nil
}

func (p *productCatalog) GetProduct(ctx context.Context, req *pb.GetProductRequest) (*pb.Product, error) {
	span := trace.SpanFromContext(ctx)
	span.SetAttributes(
		attribute.String("app.product.id", req.Id),
	)

	// GetProduct will fail on a specific product when feature flag is enabled
	if p.checkProductFailure(ctx, req.Id) {
		msg := "Error: Product Catalog Fail Feature Flag Enabled"
		span.SetStatus(otelcodes.Error, msg)
		span.AddEvent(msg)
		return nil, status.Error(codes.Internal, msg)
	}

	var found models.Product
	if err := db.
		WithContext(ctx).
		Preload("ProductPrices").
		Preload("Categories").
		Where("ID = ?", req.Id).
		First(&found).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			msg := fmt.Sprintf("Product Not Found: %s", req.Id)
			span.SetStatus(otelcodes.Error, msg)
			span.AddEvent(msg)
			return nil, status.Error(codes.NotFound, msg)
		}

		msg := "Error fetching product from the database"
		span.SetStatus(otelcodes.Error, msg)
		span.AddEvent(msg)

		return nil, status.Error(codes.Internal, msg)
	}

	product := found.ToProto()

	msg := fmt.Sprintf("Product Found - ID: %s, Name: %s", req.Id, product.Name)
	span.AddEvent(msg)
	span.SetAttributes(
		attribute.String("app.product.name", product.Name),
	)

	return product, nil
}

func (p *productCatalog) SearchProducts(ctx context.Context, req *pb.SearchProductsRequest) (*pb.SearchProductsResponse, error) {
	span := trace.SpanFromContext(ctx)

	search := fmt.Sprintf("%%%v%%", req.Query)
	var found []models.Product
	if err := db.
		WithContext(ctx).
		Preload("ProductPrices").
		Preload("Categories").
		Where("Name LIKE ?", search).
		Or("Description LIKE ?", search).
		Find(&found).Error; err != nil {
		msg := "Error searching the database"
		span.SetStatus(otelcodes.Error, msg)
		span.AddEvent(msg)

		return nil, status.Error(codes.Internal, msg)
	}

	var result []*pb.Product
	for idx := range found {
		converted := found[idx].ToProto()
		result = append(result, converted)
	}

	span.SetAttributes(
		attribute.Int("app.products_search.count", len(result)),
	)
	return &pb.SearchProductsResponse{Results: result}, nil
}

func (p *productCatalog) checkProductFailure(ctx context.Context, id string) bool {
	if id != "OLJCESPC7Z" {
		return false
	}
	failureEnabled, _ := p.client.BooleanValue(
		ctx, "productCatalogFailure", false, openfeature.EvaluationContext{},
	)
	return failureEnabled
}

func (p *productCatalog) checkProductSlowLoad(ctx context.Context) bool {
	numberVariant, err := p.client.FloatValue(
		ctx,
		"productCatalogSlowLoad",
		0,
		openfeature.EvaluationContext{},
	)
	if err != nil {
		log.Printf("Feature flag error: %v", err)
		return false
	}
	return numberVariant > 0 && rand.Float64() < numberVariant
}
