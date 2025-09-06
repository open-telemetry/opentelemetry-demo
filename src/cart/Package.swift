// swift-tools-version:6.1
import PackageDescription

let package = Package(
    name: "cart",
    platforms: [.macOS(.v15)],
    products: [
        .executable(name: "cart", targets: ["CTL"])
    ],
    dependencies: [
        .package(url: "https://github.com/apple/swift-argument-parser.git", from: "1.0.0"),
        .package(url: "https://github.com/swift-server/swift-service-lifecycle.git", from: "2.0.0"),
        .package(url: "https://github.com/grpc/grpc-swift-2.git", from: "2.0.0"),
        .package(url: "https://github.com/grpc/grpc-swift-protobuf.git", from: "2.0.0"),
        .package(url: "https://github.com/grpc/grpc-swift-nio-transport.git", from: "2.0.0"),
        .package(url: "https://github.com/grpc/grpc-swift-extras.git", from: "2.0.0"),
        .package(url: "https://github.com/swift-otel/swift-otel.git", exact: "1.0.0-alpha.2", traits: ["OTLPHTTP"]),
        .package(url: "https://github.com/swift-open-feature/swift-open-feature.git", branch: "main"),
        .package(url: "https://github.com/swift-open-feature/swift-ofrep.git", branch: "main"),
        .package(url: "https://github.com/slashmo/async-http-client.git", branch: "feature/context-propagation"),
    ],
    targets: [
        .executableTarget(
            name: "CTL",
            dependencies: [
                .product(name: "ArgumentParser", package: "swift-argument-parser"),
                .product(name: "ServiceLifecycle", package: "swift-service-lifecycle"),
                .product(name: "GRPCCore", package: "grpc-swift-2"),
                .product(name: "GRPCNIOTransportHTTP2", package: "grpc-swift-nio-transport"),
                .product(name: "GRPCProtobuf", package: "grpc-swift-protobuf"),
                .product(name: "GRPCServiceLifecycle", package: "grpc-swift-extras"),
                .product(name: "GRPCOTelTracingInterceptors", package: "grpc-swift-extras"),
                .product(name: "OTel", package: "swift-otel"),
                .product(name: "OpenFeature", package: "swift-open-feature"),
                .product(name: "OpenFeatureTracing", package: "swift-open-feature"),
                .product(name: "OFREP", package: "swift-ofrep"),
            ]
        )
    ],
    swiftLanguageModes: [.v6]
)
