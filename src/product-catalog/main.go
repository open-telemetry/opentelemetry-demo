// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
package main

import (
    "context"
    "fmt"
    "log/slog"
    "net"
    "os"
    "os/signal"
    "strings"
    "sync"
    "syscall"
    "time"

    "go.opentelemetry.io/contrib/bridges/otelslog"
    "go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc"
    "go.opentelemetry.io/contrib/instrumentation/runtime"
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/attribute"
    otelcodes "go.opentelemetry.io/otel/codes"
    "go.opentelemetry.io/otel/exporters/otlp/otlplog/otlploggrpc"
    "go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc"
    "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
    "go.opentelemetry.io/otel/exporters/stdout/stdoutlog"
    "go.opentelemetry.io/otel/log/global"
    "go.opentelemetry.io/otel/propagation"
    sdklog "go.opentelemetry.io/otel/sdk/log"
    sdkmetric "go.opentelemetry.io/otel/sdk/metric"
    sdkresource "go.opentelemetry.io/otel/sdk/resource"
    sdktrace "go.opentelemetry.io/otel/sdk/trace"
    "go.opentelemetry.io/otel/trace"

    "github.com/jackc/pgx/v5/pgxpool"
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
    logger   *slog.Logger
    catalog  []*pb.Product
    resource *sdkresource.Resource
    initResourcesOnce sync.Once
    connPool *pgxpool.Pool
)

const (
    DEFAULT_RELOAD_INTERVAL = 10
    PGX_MAX_CONNS           = 5
    PGS_MAX_CONN_LIFE_TIME  = 2 * time.Minute
    CTX_QUERY_TIMEOUT       = 10 * time.Second
)

func init() {
    logger = otelslog.NewLogger("product-catalog")
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
    consoleExporter, err := stdoutlog.New()
    if err != nil {
        return nil
    }
    loggerProvider := sdklog.NewLoggerProvider(
        sdklog.WithProcessor(sdklog.NewBatchProcessor(logExporter)),
        sdklog.WithProcessor(sdklog.NewSimpleProcessor(consoleExporter)),
    )
    global.SetLoggerProvider(loggerProvider)
    return loggerProvider
}

func initPostgresConnectionPool() *pgxpool.Pool {
    var connStr string
    mustMapEnv(&connStr, "PRODUCT_CATALOG_DB_CONNECTION")
    if connStr == "" {
        os.Exit(1)
    }
    config, err := pgxpool.ParseConfig(connStr)
    if err != nil {
        logger.Error(fmt.Sprintf("Cannot create database config: %v", err))
        os.Exit(1)
    }
    config.MaxConns = PGX_MAX_CONNS
    config.MaxConnLifetime = PGS_MAX_CONN_LIFE_TIME
    pool, err := pgxpool.NewWithConfig(context.Background(), config)
    if err != nil {
        logger.Error(fmt.Sprintf("Unable to connect to database: %v", err))
        os.Exit(1)
    }
    return pool
}

// Helper function to enrich logs with trace/span IDs
func logWithTrace(ctx context.Context, level slog.Level, msg string, attrs ...slog.Attr) {
    span := trace.SpanFromContext(ctx)
    sc := span.SpanContext()
    traceAttrs := []slog.Attr{
        slog.String("trace_id", sc.TraceID().String()),
        slog.String("span_id", sc.SpanID().String()),
    }
    logger.LogAttrs(ctx, level, msg, append(attrs, traceAttrs...)...)
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

    connPool = initPostgresConnectionPool()
    defer connPool.Close()

    err = runtime.Start(runtime.WithMinimumReadMemStatsInterval(time.Second))
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

func readProducts() ([]*pb.Product, error) {
    var products []*pb.Product
    ctx, cancelf := context.WithTimeout(context.Background(), CTX_QUERY_TIMEOUT)
    defer cancelf()
    rows, err := connPool.Query(ctx, "select value from productstate")
    if err != nil {
        logWithTrace(ctx, slog.LevelError, "error executing query", slog.String("error", err.Error()))
        return nil, status.Errorf(codes.Internal, "impossible to get products from storage")
    }
    defer rows.Close()
    for rows.Next() {
        var value []byte
        var jsonData pb.Product
        err := rows.Scan(&value)
        if err != nil {
            logWithTrace(ctx, slog.LevelError, "error parsing row", slog.String("error", err.Error()))
            return nil, status.Errorf(codes.Internal, "error getting data from row")
        }
        err = protojson.Unmarshal(value, &jsonData)
        if err != nil {
            logWithTrace(ctx, slog.LevelError, "error unmarshal", slog.String("error", err.Error()))
            return nil, status.Errorf(codes.Internal, "error parsing the data")
        }
        products = append(products, &jsonData)
    }
    return products, nil
}

func readProduct(productId string) (*pb.Product, error) {
    var value []byte
    var jsonData pb.Product
    ctx, cancelf := context.WithTimeout(context.Background(), CTX_QUERY_TIMEOUT)
    defer cancelf()
    err := connPool.QueryRow(ctx, "select value from productstate where key = $1", productId).Scan(&value)
    if err != nil {
        logWithTrace(ctx, slog.LevelError, "error executing query", slog.String("error", err.Error()))
        return nil, status.Errorf(codes.Internal, "impossible to get product for id %s", productId)
    }
    err = protojson.Unmarshal(value, &jsonData)
    if err != nil {
        logWithTrace(ctx, slog.LevelError, "error unmarshal", slog.String("error", err.Error()))
        return nil, status.Errorf(codes.Internal, "error parsing the data")
    }
    return &jsonData, nil
}

func mustMapEnv(target *string, key string) {
    value, present := os.LookupEnv(key)
    if !present {
        logger.Error(fmt.Sprintf("Environment Variable Not Set: %q", key))
    }
    *target = value
}

func (p *productCatalog) ListProducts(ctx context.Context, req *pb.Empty) (*pb.ListProductsResponse, error) {
    span := trace.SpanFromContext(ctx)
    span.SetAttributes(attribute.Int("app.products.count", len(catalog)))
    logWithTrace(ctx, slog.LevelInfo, "List products")
    startTime := time.Now()
    products, err := readProducts()
    if err != nil {
        logWithTrace(ctx, slog.LevelError, "Can't get products in ListProducts", slog.String("error", err.Error()))
        return nil, err
    }
    logWithTrace(ctx, slog.LevelInfo, "Number of products read", slog.Int("count", len(products)), slog.String("duration", time.Since(startTime).String()))
    return &pb.ListProductsResponse{Products: products}, nil
}

func (p *productCatalog) GetProduct(ctx context.Context, req *pb.GetProductRequest) (*pb.Product, error) {
    span := trace.SpanFromContext(ctx)
    span.SetAttributes(attribute.String("app.product.id", req.Id))
    logWithTrace(ctx, slog.LevelInfo, "[GetProduct]", slog.String("product.id", req.Id))
    if p.checkProductFailure(ctx, req.Id) {
        msg := "Error: Product Catalog Fail Feature Flag Enabled"
        span.SetStatus(otelcodes.Error, msg)
        span.AddEvent(msg)
        return nil, status.Errorf(codes.Internal, msg)
    }
    startTime := time.Now()
    found, err := readProduct(req.Id)
    if err != nil {
        logWithTrace(ctx, slog.LevelError, "Can't get product in GetProduct", slog.String("id", req.Id), slog.String("error", err.Error()))
        return nil, err
    }
    logWithTrace(ctx, slog.LevelInfo, "Product details read", slog.String("duration", time.Since(startTime).String()))
    if found == nil {
        msg := fmt.Sprintf("Product Not Found: %s", req.Id)
        span.SetStatus(otelcodes.Error, msg)
        span.AddEvent(msg)
        return nil, status.Errorf(codes.NotFound, msg)
    }
    span.AddEvent("Product Found")
    span.SetAttributes(attribute.String("app.product.id", req.Id), attribute.String("app.product.name", found.Name))
    logWithTrace(ctx, slog.LevelInfo, "Product Found", slog.String("app.product.name", found.Name), slog.String("app.product.id", req.Id))
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
    span.SetAttributes(attribute.Int("app.products_search.count", len(result)))
    logWithTrace(ctx, slog.LevelInfo, "SearchProducts executed", slog.Int("results", len(result)))
    return &pb.SearchProductsResponse{Results: result}, nil
}

func (p *productCatalog) checkProductFailure(ctx context.Context, id string) bool {
    if id != "OLJCESPC7Z" {
        return false
    }
    client := openfeature.NewClient("productCatalog")
    failureEnabled, _ := client.BooleanValue(ctx, "productCatalogFailure", false, openfeature.EvaluationContext{})
    return failureEnabled
}

func createClient(ctx context.Context, svcAddr string) (*grpc.ClientConn, error) {
    return grpc.DialContext(ctx, svcAddr,
        grpc.WithTransportCredentials(insecure.NewCredentials()),
        grpc.WithStatsHandler(otelgrpc.NewClientHandler()),
    )
}