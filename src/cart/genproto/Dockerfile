FROM swift:6.1

WORKDIR /app

RUN apt-get update && \
    apt-get install -y protobuf-compiler

COPY ./pb/ /build/pb/

COPY ./src/cart/Package.swift Package.swift
COPY ./src/cart/Package.resolved Package.resolved

RUN swift package resolve

COPY ./src/cart .

RUN swift build --product protoc-gen-swift
RUN swift build --product protoc-gen-grpc-swift-2
