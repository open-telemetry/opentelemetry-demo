#!/bin/sh

set -euo pipefail

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# This script is used to update generated code after changing demo.proto.

cd -P -- "$(dirname -- "$0")"
pwd

command -v npm >/dev/null 2>&1 || {
  cat <<EOF >&2
npm needs to be installed but it isn't.

Aborting.
EOF
  exit 1
}

command -v go >/dev/null 2>&1 || {
  cat <<EOF >&2
go needs to be installed but it isn't.

Aborting.
EOF
  exit 1
}

command -v rebar3 >/dev/null 2>&1 || {
  cat <<EOF >&2
rebar3 needs to be installed but it isn't.

Aborting.
EOF
  exit 1
}


command -v protoc >/dev/null 2>&1 || {
  cat <<EOF >&2
protoc needs to be installed but it isn't.

Aborting.
EOF
  exit 1
}

echo "Regenerating typescript code in src/frontend based on demo.proto"
pushd src/frontend > /dev/null
# The npm script grpc:generate expects the pb directory to be available in the current directory (src/frontend) because it is
# intended to be used during Docker build, where pb is copied to the same working directory as src/frontend. To get around that
# difference, we temporarily create a symlink to pb and then remove it after the script is done.
ln -s ../../pb pb
npm run grpc:generate
rm pb
popd > /dev/null

echo "Regenerating Go code in src/accountingservice based on demo.proto"
pushd src/accountingservice > /dev/null
go generate
popd > /dev/null

echo "Regenerating Go code in src/checkoutservice based on demo.proto"
pushd src/checkoutservice > /dev/null
go generate
popd > /dev/null

echo "Regenerating Go code in src/productcatalogservice based on demo.proto"
pushd src/productcatalogservice > /dev/null
go generate
popd > /dev/null

echo "Regenerating Java code in src/adservice based on demo.proto"
pushd src/adservice > /dev/null
./gradlew  generateProto
popd > /dev/null

echo "Recompiling Erlang code in src/featureflagservice based on demo.proto"
pushd src/featureflagservice > /dev/null
# The Erlang build expects the proto file to be available in src/featureflagservice/proto) because it is
# intended to be used during Docker build, where demo.proto is copied to the the proto directory in the same working directory
# as the Erlang source code. To get around that difference, we temporarily create a symlink to ../../pb as proto and then remove
# it after the script is done.
ln -s ../../pb proto
rebar3 grpc_regen
rm proto
popd > /dev/null


echo done