#!/bin/sh
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

set -e # Exit immediately if a command exits with a non-zero status.
set -x # Print commands and their arguments as they are executed

# This script is used to generate protobuf files for all services with Docker.

gen_proto_go() {
  echo "Generating Go protobuf files for $1"
  docker build -f "src/$1/genproto/Dockerfile" -t "$1-genproto" .
  docker run --rm -v $(pwd):/build "$1-genproto" \
    protoc -I /build/pb /build/pb/demo.proto --go_out="./src/$1/" --go-grpc_out="./src/$1/"
}

gen_proto_python() {
  echo "Generating Python protobuf files for $1"
  docker build -f "src/$1/genproto/Dockerfile" -t "$1-genproto" .
  docker run --rm -v $(pwd):/build "$1-genproto" \
    python -m grpc_tools.protoc -I /build/pb/ --python_out="./src/$1/" --grpc_python_out="./src/$1/" /build/pb/demo.proto
}

#gen_proto_dotnet accounting
#gen_proto_java ad
#gen_proto_dotnet cart
gen_proto_go checkoutservice
#gen_proto_cpp currency
#gen_proto_ruby email
#gen_proto_ts frontend
#gen_proto_js paymentservice
gen_proto_go productcatalogservice
#gen_proto_php quote
gen_proto_python recommendationservice
#gen_proto_rust shipping
