// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

//go:build tools
// +build tools

package tools

import (
	_ "google.golang.org/grpc/cmd/protoc-gen-go-grpc"
	_ "google.golang.org/protobuf/cmd/protoc-gen-go"
)
