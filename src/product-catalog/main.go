// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
package main

//go:generate go install google.golang.org/protobuf/cmd/protoc-gen-go
//go:generate go install google.golang.org/grpc/cmd/protoc-gen-go-grpc
//go:generate protoc --go_out=./ --go-grpc_out=./ --proto_path=../../pb ../../pb/demo.proto

import (
	"context"
	"fmt"
	"io/fs"
	"log/slog"
	"net"
	"os"
	"os/signal"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	"go.opentelemetry.io/contrib/bridges/otelslog"
	"go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc"
	otelruntime "go.opentelemetry.io/contrib/instrumentation/runtime"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	otelcodes "go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/exporters/otlp/otlplog/otlploggrpc"
	"go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/log/global"
	"go.opentelemetry.io/otel/propagation"
	sdklog "go.opentelemetry.io/otel/sdk/log"
	sdkmetric "go.opentelemetry.io/otel/sdk/metric"
	sdkresource "go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	"go.opentelemetry.io/otel/trace"

	otelhooks "github.com/open-feature/go-sdk-contrib/hooks/open-telemetry/pkg"
	flagd "github.com/open-feature/go-sdk-contrib/providers/flagd/pkg"
	"github.com/open-feature/go-sdk/openfeature"
	pb "github.com/opentelemetry/opentelemetry-demo/src/product-catalog/genproto/oteldemo"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/health"
	healthpb "google.golang.org/grpc/health/grpc_health_v1"
	"google.golang.org/grpc/reflection"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/encoding/protojson"
)

var (
	logger            *slog.Logger
	catalog           []*pb.Product
	resource          *sdkresource.Resource
	initResourcesOnce sync.Once
)

const DEFAULT_RELOAD_INTERVAL = 10

func init() {
	logger = otelslog.NewLogger("product-catalog")

	loadProductCatalog()
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
		logger.Error(fmt.Sprintf("OTLP Trace gRPC Creation: %v", err))

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

func main() {
	lp := initLoggerProvider()
	defer func() {
		if err := lp.Shutdown(context.Background()); err != nil {
			logger.Error(fmt.Sprintf("Logger Provider Shutdown: %v", err))
		}
		logger.Info("Shutdown logger provider")
	}()

	tp := initTracerProvider()
	defer func() {
		if err := tp.Shutdown(context.Background()); err != nil {
			logger.Error(fmt.Sprintf("Tracer Provider Shutdown: %v", err))
		}
		logger.Info("Shutdown tracer provider")
	}()

	mp := initMeterProvider()
	defer func() {
		if err := mp.Shutdown(context.Background()); err != nil {
			logger.Error(fmt.Sprintf("Error shutting down meter provider: %v", err))
		}
		logger.Info("Shutdown meter provider")
	}()
	openfeature.AddHooks(otelhooks.NewTracesHook())
	provider, err := flagd.NewProvider()
	if err != nil {
		logger.Error(err.Error())
	}
	err = openfeature.SetProvider(provider)
	if err != nil {
		logger.Error(err.Error())
	}

	err = otelruntime.Start(otelruntime.WithMinimumReadMemStatsInterval(time.Second))
	if err != nil {
		logger.Error(err.Error())
	}

	svc := &productCatalog{}
	var port string
	mustMapEnv(&port, "PRODUCT_CATALOG_PORT")

	logger.Info(fmt.Sprintf("Product Catalog gRPC server started on port: %s", port))

	ln, err := net.Listen("tcp", fmt.Sprintf(":%s", port))
	if err != nil {
		logger.Error(fmt.Sprintf("TCP Listen: %v", err))
	}

	srv := grpc.NewServer(
		grpc.StatsHandler(otelgrpc.NewServerHandler()),
	)

	reflection.Register(srv)

	pb.RegisterProductCatalogServiceServer(srv, svc)

	healthcheck := health.NewServer()
	healthpb.RegisterHealthServer(srv, healthcheck)

	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM, syscall.SIGKILL)
	defer cancel()

	go func() {
		if err := srv.Serve(ln); err != nil {
			logger.Error(fmt.Sprintf("Failed to serve gRPC server, err: %v", err))
		}
	}()

	<-ctx.Done()

	srv.GracefulStop()
	logger.Info("Product Catalog gRPC server stopped")
}

type productCatalog struct {
	pb.UnimplementedProductCatalogServiceServer
}

func loadProductCatalog() {
	logger.Info("Loading Product Catalog...")
	var err error
	catalog, err = readProductFiles()
	if err != nil {
		logger.Error(fmt.Sprintf("Error reading product files: %v\n", err))
		os.Exit(1)
	}

	// Default reload interval is 10 seconds
	interval := DEFAULT_RELOAD_INTERVAL
	si := os.Getenv("PRODUCT_CATALOG_RELOAD_INTERVAL")
	if si != "" {
		interval, _ = strconv.Atoi(si)
		if interval <= 0 {
			interval = DEFAULT_RELOAD_INTERVAL
		}
	}
	logger.Info(fmt.Sprintf("Product Catalog reload interval: %d", interval))

	ticker := time.NewTicker(time.Duration(interval) * time.Second)

	go func() {
		for {
			select {
			case <-ticker.C:
				logger.Info("Reloading Product Catalog...")
				catalog, err = readProductFiles()
				if err != nil {
					logger.Error(fmt.Sprintf("Error reading product files: %v", err))
					continue
				}
			}
		}
	}()
}

func readProductFiles() ([]*pb.Product, error) {

	// find all .json files in the products directory
	entries, err := os.ReadDir("./products")
	if err != nil {
		return nil, err
	}

	jsonFiles := make([]fs.FileInfo, 0, len(entries))
	for _, entry := range entries {
		if strings.HasSuffix(entry.Name(), ".json") {
			info, err := entry.Info()
			if err != nil {
				return nil, err
			}
			jsonFiles = append(jsonFiles, info)
		}
	}

	// read the contents of each .json file and unmarshal into a ListProductsResponse
	// then append the products to the catalog
	var products []*pb.Product
	for _, f := range jsonFiles {
		jsonData, err := os.ReadFile("./products/" + f.Name())
		if err != nil {
			return nil, err
		}

		var res pb.ListProductsResponse
		if err := protojson.Unmarshal(jsonData, &res); err != nil {
			return nil, err
		}

		products = append(products, res.Products...)
	}

	logger.LogAttrs(
		context.Background(),
		slog.LevelInfo,
		fmt.Sprintf("Loaded %d products\n", len(products)),
		slog.Int("products", len(products)),
	)

	return products, nil
}

func getTraceContext(ctx context.Context) map[string]interface{} {
	span := trace.SpanFromContext(ctx)
	spanContext := span.SpanContext()
	
	return map[string]interface{}{
		"traceId":    spanContext.TraceID().String(),
		"spanId":     spanContext.SpanID().String(),
		"traceFlags": spanContext.TraceFlags(),
		"isValid":    spanContext.IsValid(),
	}
}

func getSystemMetrics() map[string]interface{} {
	var memStats runtime.MemStats
	runtime.ReadMemStats(&memStats)
	
	return map[string]interface{}{
		"memory": map[string]interface{}{
			"alloc_mb":         float64(memStats.Alloc) / 1024 / 1024,
			"total_alloc_mb":   float64(memStats.TotalAlloc) / 1024 / 1024,
			"sys_mb":           float64(memStats.Sys) / 1024 / 1024,
			"heap_alloc_mb":    float64(memStats.HeapAlloc) / 1024 / 1024,
			"heap_sys_mb":      float64(memStats.HeapSys) / 1024 / 1024,
			"heap_idle_mb":     float64(memStats.HeapIdle) / 1024 / 1024,
			"heap_inuse_mb":    float64(memStats.HeapInuse) / 1024 / 1024,
			"heap_released_mb": float64(memStats.HeapReleased) / 1024 / 1024,
			"stack_inuse_mb":   float64(memStats.StackInuse) / 1024 / 1024,
			"stack_sys_mb":     float64(memStats.StackSys) / 1024 / 1024,
		},
		"gc": map[string]interface{}{
			"num_gc":           memStats.NumGC,
			"pause_total_ns":   memStats.PauseTotalNs,
			"pause_ns":         memStats.PauseNs,
			"gc_cpu_fraction":  memStats.GCCPUFraction,
			"next_gc_mb":       float64(memStats.NextGC) / 1024 / 1024,
			"last_gc":          time.Unix(0, int64(memStats.LastGC)).Format(time.RFC3339),
		},
		"performance": map[string]interface{}{
			"goroutines":     runtime.NumGoroutine(),
			"num_cpu":        runtime.NumCPU(),
			"gomaxprocs":     runtime.GOMAXPROCS(0),
			"num_cgo_calls":  runtime.NumCgoCall(),
		},
		"process": map[string]interface{}{
			"go_version": runtime.Version(),
			"goos":       runtime.GOOS,
			"goarch":     runtime.GOARCH,
		},
		"timestamp": time.Now().Unix(),
	}
}

func mustMapEnv(target *string, key string) {
	value, present := os.LookupEnv(key)
	if !present {
		logger.Error(fmt.Sprintf("Environment Variable Not Set: %q", key))
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
	return &pb.ListProductsResponse{Products: catalog}, nil
}

func (p *productCatalog) GetProduct(ctx context.Context, req *pb.GetProductRequest) (*pb.Product, error) {
	startTime := time.Now()
	span := trace.SpanFromContext(ctx)
	span.SetAttributes(
		attribute.String("app.product.id", req.Id),
	)

	// GetProduct will fail on a specific product when feature flag is enabled
	if p.checkProductFailure(ctx, req.Id) {
		operationDuration := time.Since(startTime)
		traceContext := getTraceContext(ctx)
		systemMetrics := getSystemMetrics()
		
		// Enhanced logging for product catalog failure scenario
		logger.LogAttrs(
			ctx,
			slog.LevelError,
			"Product lookup failed due to catalog service error",
			slog.String("error.type", "ProductCatalogServiceError"),
			slog.String("error.code", "CATALOG_LOOKUP_FAILED"),
			slog.String("product.id", req.Id),
			slog.String("product.lookup_status", "failed"),
			slog.Int("catalog.total_products", len(catalog)),
			slog.String("catalog.state", "operational"),
			slog.String("operation", "GetProduct"),
			slog.String("failure.reason", "Product retrieval service temporarily unavailable"),
			slog.String("failure.context", "Database connection timeout during product lookup"),
			slog.String("system.component", "product-catalog-service"),
			slog.String("service", "product-catalog-service"),
			slog.Float64("operation_duration_ms", float64(operationDuration.Nanoseconds())/1000000),
			slog.String("performance.latency", "elevated"),
			slog.Any("trace_context", traceContext),
			slog.Any("system_metrics", systemMetrics),
		)

		// Log additional context about the specific product that failed
		logger.LogAttrs(
			ctx,
			slog.LevelError,
			"Product retrieval attempt details",
			slog.String("product.target_id", "OLJCESPC7Z"),
			slog.String("product.category", "unknown - lookup failed"),
			slog.String("retrieval.attempt_time", time.Now().Format(time.RFC3339)),
			slog.String("database.connection_status", "timeout"),
			slog.String("database.last_successful_query", "unknown"),
			slog.Int("database.active_connections", 0),
			slog.String("error.stack_trace", "ProductCatalogService.GetProduct() -> DatabaseConnection.timeout"),
			slog.String("service", "product-catalog-service"),
			slog.Float64("database_timeout_duration_ms", float64(operationDuration.Nanoseconds())/1000000),
			slog.String("performance.database_latency", "timeout"),
			slog.Any("trace_context", traceContext),
			slog.Any("system_metrics", systemMetrics),
		)

		msg := "Product retrieval failed: database connection timeout during lookup operation"
		span.SetStatus(otelcodes.Error, msg)
		span.AddEvent(msg)
		return nil, status.Errorf(codes.Internal, msg)
	}

	var found *pb.Product
	for _, product := range catalog {
		if req.Id == product.Id {
			found = product
			break
		}
	}

	if found == nil {
		operationDuration := time.Since(startTime)
		traceContext := getTraceContext(ctx)
		systemMetrics := getSystemMetrics()
		
		// Enhanced logging for product not found scenario
		logger.LogAttrs(
			ctx,
			slog.LevelError,
			"Product not found in catalog",
			slog.String("error.type", "ProductNotFoundError"),
			slog.String("error.code", "PRODUCT_NOT_FOUND"),
			slog.String("product.requested_id", req.Id),
			slog.String("product.lookup_status", "not_found"),
			slog.Int("catalog.total_products", len(catalog)),
			slog.String("catalog.state", "loaded"),
			slog.String("catalog.last_reload", time.Now().Add(-time.Duration(DEFAULT_RELOAD_INTERVAL)*time.Second).Format(time.RFC3339)),
			slog.String("operation", "GetProduct"),
			slog.String("search.method", "linear_scan"),
			slog.String("search.scope", "full_catalog"),
			slog.String("service", "product-catalog-service"),
			slog.Float64("search_duration_ms", float64(operationDuration.Nanoseconds())/1000000),
			slog.String("performance.search_latency", "normal"),
			slog.Any("trace_context", traceContext),
			slog.Any("system_metrics", systemMetrics),
		)

		// Log catalog metadata and system state
		logger.LogAttrs(
			ctx,
			slog.LevelError,
			"Product catalog state during lookup failure",
			slog.String("catalog.source", "./products/*.json"),
			slog.String("catalog.format", "protobuf_json"),
			slog.String("system.component", "product-catalog-service"),
			slog.String("request.context", fmt.Sprintf("Client requested product ID: %s", req.Id)),
			slog.String("available_products", fmt.Sprintf("Catalog contains %d products", len(catalog))),
			slog.String("lookup.algorithm", "sequential_search"),
			slog.String("system.health", "operational"),
			slog.String("service", "product-catalog-service"),
			slog.Float64("catalog_scan_duration_ms", float64(operationDuration.Nanoseconds())/1000000),
			slog.String("performance.catalog_efficiency", "normal"),
			slog.Any("trace_context", traceContext),
			slog.Any("system_metrics", systemMetrics),
		)

		msg := fmt.Sprintf("Product Not Found: %s", req.Id)
		span.SetStatus(otelcodes.Error, msg)
		span.AddEvent(msg)
		return nil, status.Errorf(codes.NotFound, msg)
	}

	span.AddEvent("Product Found")
	span.SetAttributes(
		attribute.String("app.product.id", req.Id),
		attribute.String("app.product.name", found.Name),
	)

	// Enhanced logging for successful product retrieval
	operationDuration := time.Since(startTime)
	traceContext := getTraceContext(ctx)
	systemMetrics := getSystemMetrics()
	
	logger.LogAttrs(
		ctx,
		slog.LevelInfo, "Product successfully retrieved",
		slog.String("product.id", found.Id),
		slog.String("product.name", found.Name),
		slog.String("product.description", found.Description),
		slog.String("product.picture", found.Picture),
		slog.String("product.categories", strings.Join(found.Categories, ",")),
		slog.String("operation", "GetProduct"),
		slog.String("operation.status", "success"),
		slog.Int("catalog.total_products", len(catalog)),
		slog.String("lookup.method", "sequential_search"),
		slog.String("system.component", "product-catalog-service"),
		slog.String("request.context", fmt.Sprintf("Successfully found product: %s", req.Id)),
		slog.String("service", "product-catalog-service"),
		slog.Float64("lookup_duration_ms", float64(operationDuration.Nanoseconds())/1000000),
		slog.String("performance.lookup_latency", "normal"),
		slog.Any("trace_context", traceContext),
		slog.Any("system_metrics", systemMetrics),
	)

	return found, nil
}

func (p *productCatalog) SearchProducts(ctx context.Context, req *pb.SearchProductsRequest) (*pb.SearchProductsResponse, error) {
	span := trace.SpanFromContext(ctx)

	var result []*pb.Product
	for _, product := range catalog {
		if strings.Contains(strings.ToLower(product.Name), strings.ToLower(req.Query)) ||
			strings.Contains(strings.ToLower(product.Description), strings.ToLower(req.Query)) {
			result = append(result, product)
		}
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

	client := openfeature.NewClient("productCatalog")
	failureEnabled, _ := client.BooleanValue(
		ctx, "productCatalogFailure", false, openfeature.EvaluationContext{},
	)
	return failureEnabled
}

func createClient(ctx context.Context, svcAddr string) (*grpc.ClientConn, error) {
	return grpc.DialContext(ctx, svcAddr,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithStatsHandler(otelgrpc.NewClientHandler()),
	)
}
