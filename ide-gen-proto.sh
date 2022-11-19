#!/bin/sh

base_dir=$(pwd)

gen_proto_dotnet() {
  cd "$base_dir"/src/"$1" || return
  mkdir -p ./src/protos/
  cp -r "$base_dir"/pb/ ./src/protos/
  cd "$base_dir" || return
}

gen_proto_elixir() {
  cd "$base_dir"/src/"$1" || return
  cp "$base_dir"/pb/demo.proto ./proto/demo.proto
  rebar3 grpc gen
  cd "$base_dir" || return
}

gen_proto_go() {
  cd "$base_dir"/src/"$1" || return
  protoc -I ../../pb ./../../pb/demo.proto --go_out=./ --go-grpc_out=./
  cd "$base_dir" || return
}

gen_proto_js() {
  cd "$base_dir"/src/"$1" || return
  cp "$base_dir"/pb/demo.proto .
  cd "$base_dir" || return
}

gen_proto_python() {
  cd "$base_dir"/src/"$1" || return
  python -m grpc_tools.protoc -I=../../pb --python_out=./ --grpc_python_out=./ ./../../pb/demo.proto
  cd "$base_dir" || return
}

gen_proto_rust() {
  cd "$base_dir"/src/"$1" || return
  mkdir -p proto
  cp "$base_dir"/pb/demo.proto proto/demo.proto
  cargo build
  cd "$base_dir" || return
}

gen_proto_ts() {
  cd "$base_dir"/src/"$1" || return
  cp -r "$base_dir"/pb .
  cd "$base_dir" || return
}

# gen_proto_java adservice
gen_proto_dotnet cartservice
gen_proto_go checkoutservice
# gen_proto_cpp currencyservice
# gen_proto_ruby emailservice
# gen_proto_elixir featureflagservice
gen_proto_ts frontend
gen_proto_js paymentservice
gen_proto_go productcatalogservice
# gen_proto_php quoteservice
gen_proto_python recommendationservice
gen_proto_rust shippingservice
