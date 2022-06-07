# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

FROM golang:1.17.7-alpine AS builder

RUN apk add build-base protoc

WORKDIR /usr/src/app/

# Restore dependencies
COPY ./src/frontend/ ./
COPY ./pb/ ./proto/
RUN go mod download
RUN go get google.golang.org/protobuf/cmd/protoc-gen-go
RUN go get google.golang.org/grpc/cmd/protoc-gen-go-grpc

# Build executable
RUN protoc -I ./proto/ ./proto/demo.proto --go_out=./ --go-grpc_out=./
RUN go build -o /go/bin/frontend/ ./

# -----------------------------------------------------------------------------

FROM alpine

RUN apk add busybox-extras net-tools bind-tools
WORKDIR /usr/src/app/

COPY --from=builder /go/bin/frontend/ ./
COPY ./src/frontend/templates/ ./templates/
COPY ./src/frontend/static/ ./static/

EXPOSE ${FRONTEND_PORT}
ENTRYPOINT [ "./frontend" ]
