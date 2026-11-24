// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
package main

import (
	"bytes"
	"context"
	"database/sql"
	"database/sql/driver"
	"errors"
	"io"
	"log/slog"
	"strings"
	"testing"
	"time"

	"github.com/open-feature/go-sdk/openfeature"
	"github.com/open-feature/go-sdk/openfeature/memprovider"
	pb "github.com/opentelemetry/opentelemetry-demo/src/product-catalog/genproto/oteldemo"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

type testConnector struct{ queryErr error }

func (c testConnector) Connect(context.Context) (driver.Conn, error) {
	return testConn{queryErr: c.queryErr}, nil
}
func (testConnector) Driver() driver.Driver { return testDriver{} }

type testDriver struct{}

func (testDriver) Open(string) (driver.Conn, error) { return testConn{}, nil }

type testConn struct{ queryErr error }

func (testConn) Prepare(string) (driver.Stmt, error) { return nil, errors.New("unexpected prepare") }
func (testConn) Close() error                        { return nil }
func (testConn) Begin() (driver.Tx, error)           { return nil, errors.New("unexpected transaction") }
func (c testConn) QueryContext(context.Context, string, []driver.NamedValue) (driver.Rows, error) {
	if c.queryErr != nil {
		return nil, c.queryErr
	}
	return emptyRows{}, nil
}

type emptyRows struct{}

func (emptyRows) Columns() []string         { return []string{"id"} }
func (emptyRows) Close() error              { return nil }
func (emptyRows) Next([]driver.Value) error { return io.EOF }

func setupLogTest(t *testing.T, queryErr error) *bytes.Buffer {
	t.Helper()
	oldDB, oldLogger := db, logger
	db = sql.OpenDB(testConnector{queryErr: queryErr})
	var buf bytes.Buffer
	logger = slog.New(slog.NewJSONHandler(&buf, nil))
	t.Cleanup(func() {
		db.Close()
		db, logger = oldDB, oldLogger
	})
	return &buf
}

func TestGetProductLookupLogsDistinguishMissingFromDatabaseFailure(t *testing.T) {
	for _, tt := range []struct {
		name     string
		queryErr error
		want     string
		wantCode codes.Code
	}{
		{name: "missing", want: `"msg":"product not found"`, wantCode: codes.NotFound},
		{name: "database failure", queryErr: errors.New("database unavailable"), want: `"error":"failed to scan product row: database unavailable"`, wantCode: codes.Internal},
		{name: "canceled", queryErr: context.Canceled, want: `"msg":"failed to query product"`, wantCode: codes.Canceled},
		{name: "deadline exceeded", queryErr: context.DeadlineExceeded, want: `"msg":"failed to query product"`, wantCode: codes.DeadlineExceeded},
	} {
		t.Run(tt.name, func(t *testing.T) {
			buf := setupLogTest(t, tt.queryErr)
			_, err := (&productCatalog{}).GetProduct(context.Background(), &pb.GetProductRequest{Id: "test-product"})
			if status.Code(err) != tt.wantCode {
				t.Fatalf("GetProduct() code = %v, want %v", status.Code(err), tt.wantCode)
			}
			if tt.wantCode == codes.Internal && status.Convert(err).Message() != "failed to query product" {
				t.Errorf("GetProduct() exposed database error: %v", err)
			}
			if !strings.Contains(buf.String(), tt.want) {
				t.Errorf("log = %s, want %s", buf.String(), tt.want)
			}
			if tt.queryErr != nil && strings.Contains(buf.String(), `"msg":"product not found"`) {
				t.Errorf("database error incorrectly logged as missing product: %s", buf.String())
			}
		})
	}
}

func TestSearchLogsDoNotIncludeQuery(t *testing.T) {
	buf := setupLogTest(t, nil)
	const query = "sensitive-search-marker"
	_, err := (&productCatalog{}).SearchProducts(context.Background(), &pb.SearchProductsRequest{Query: query})
	if err != nil {
		t.Fatalf("SearchProducts() error = %v", err)
	}
	if strings.Contains(buf.String(), query) {
		t.Errorf("search query appeared in logs: %s", buf.String())
	}
	if !strings.Contains(buf.String(), `"demo.product.search.count":0`) {
		t.Errorf("search result count missing from log: %s", buf.String())
	}
}

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
