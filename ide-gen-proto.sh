# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0
#!/bin/sh


# This script is used to generate protobuf files for all services.
# Useful to ensure code can compile without Docker, and provide hints for IDEs.
# Several dev tools including: cargo, protoc, python grpcio-tools, and rebar3 may be required to run this script.

base_dir=$(pwd)

gen_proto_dotnet() {
  echo "Generating .NET protobuf files for $1"
  cd "$base_dir"/src/"$1" || return
  mkdir -p ./src/protos/
  cp -r "$base_dir"/pb/ ./src/protos/
  cd "$base_dir" || return
}

gen_proto_elixir() {
  echo "Generating Elixir protobuf files for $1"
  cd "$base_dir"/src/"$1" || return
  mkdir -p proto
  cp "$base_dir"/pb/demo.proto ./proto/demo.proto
  rebar3 grpc_regen
  cd "$base_dir" || return
}

gen_proto_go() {
  echo "Generating Go protobuf files for $1"
  cd "$base_dir"/src/"$1" || return
  protoc -I ../../pb ./../../pb/demo.proto --go_out=./ --go-grpc_out=./
  cd "$base_dir" || return
}

gen_proto_js() {
  echo "Generating Javascript protobuf files for $1"
  cd "$base_dir"/src/"$1" || return
  cp "$base_dir"/pb/demo.proto .
  cd "$base_dir" || return
}

gen_proto_python() {
  echo "Generating Python protobuf files for $1"
  cd "$base_dir"/src/"$1" || return
  python3 -m grpc_tools.protoc -I=../../pb --python_out=./ --grpc_python_out=./ ./../../pb/demo.proto
  cd "$base_dir" || return
}

gen_proto_rust() {
  echo "Generating Rust protobuf files for $1"
  cd "$base_dir"/src/"$1" || return
  mkdir -p proto
  cp "$base_dir"/pb/demo.proto proto/demo.proto
  cargo build
  cd "$base_dir" || return
}

gen_proto_ts() {
  echo "Generating Typescript protobuf files for $1"
  cd "$base_dir"/src/"$1" || return
  cp -r "$base_dir"/pb .
  mkdir -p ./protos
  protoc -I ./pb  --plugin=./node_modules/.bin/protoc-gen-ts_proto --ts_proto_opt=esModuleInterop=true --ts_proto_out=./protos --ts_proto_opt=outputServices=grpc-js demo.proto
  cd "$base_dir" || return
}

gen_proto_go accountingservice
# gen_proto_java adservice
gen_proto_dotnet cartservice
gen_proto_go checkoutservice
# gen_proto_cpp currencyservice
# gen_proto_ruby emailservice
gen_proto_elixir featureflagservice
gen_proto_ts frontend
gen_proto_js paymentservice
gen_proto_go productcatalogservice
# gen_proto_php quoteservice
gen_proto_python recommendationservice
gen_proto_rust shippingservice
