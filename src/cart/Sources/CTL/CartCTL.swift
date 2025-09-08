import ArgumentParser
import Foundation
import Logging
import GRPCCore
import GRPCNIOTransportHTTP2
import ServiceLifecycle
import GRPCServiceLifecycle
import GRPCOTelTracingInterceptors
import OTel
import OpenFeature
import OpenFeatureTracing
import OFREP
import Tracing
import Valkey

@main
struct CartCTL: AsyncParsableCommand {
    func run() async throws {
        let observability = try OTel.bootstrap()
        let logger = Logger(label: "cart")

        guard let port = ProcessInfo.processInfo.environment["CART_PORT"].flatMap(Int.init),
              let ofrepHost = ProcessInfo.processInfo.environment["FLAGD_HOST"],
              let ofrepPort = ProcessInfo.processInfo.environment["FLAGD_OFREP_PORT"],
              let valkeyHost = ProcessInfo.processInfo.environment["VALKEY_HOST"],
              let valkeyPort = ProcessInfo.processInfo.environment["VALKEY_PORT"].flatMap(Int.init) else {
            Self.exit()
        }

        let valkeyClient = ValkeyClient(.hostname(valkeyHost, port: valkeyPort), logger: logger)

        let ofrepProvider = OFREPProvider(serverURL: URL(string: "http://\(ofrepHost):\(ofrepPort)")!)
        OpenFeatureSystem.setProvider(ofrepProvider)
        OpenFeatureSystem.addHooks([OpenFeatureTracingHook()])

        let service = CartService(
            openFeatureClient: OpenFeatureSystem.client(),
            valkeyClient: valkeyClient
        )
        let server = GRPCServer(
            transport: .http2NIOPosix(
                address: .ipv4(host: "0.0.0.0", port: port),
                transportSecurity: .plaintext
            ),
            services: [service],
            interceptors: [ServerOTelTracingInterceptor(serverHostname: "0.0.0.0", networkTransportMethod: "tcp")]
        )

        let serviceGroup = ServiceGroup(
            services: [observability, valkeyClient, ofrepProvider, server],
            gracefulShutdownSignals: [.sigint, .sigterm],
            logger: Logger(label: "cart")
        )

        try await serviceGroup.run()
    }
}

struct CartService: Oteldemo_CartService.SimpleServiceProtocol {
    let openFeatureClient: OpenFeatureClient
    let valkeyClient: ValkeyClient
    private let logger = Logger(label: "CartService")

    func addItem(
        request: Oteldemo_AddItemRequest,
        context: ServerContext
    ) async throws -> Oteldemo_Empty {
        var cart = try await cart(userID: request.userID) ?? Oteldemo_Cart.with { $0.userID = request.userID }

        if let existingIndex = cart.items.firstIndex(where: { $0.productID == request.item.productID }) {
            cart.items[existingIndex].quantity += request.item.quantity
        } else {
            cart.items.append(request.item)
        }

        let serializedCart: [UInt8] = try cart.serializedBytes()
        try await valkeyClient.hset(ValkeyKey(request.userID), data: [.init(field: "cart", value: serializedCart)])
        try await valkeyClient.expire(ValkeyKey(request.userID), seconds: 60 * 60)

        return Oteldemo_Empty()
    }

    func getCart(
        request: Oteldemo_GetCartRequest,
        context: ServerContext
    ) async throws -> Oteldemo_Cart {
        logger.info("Fetch cart.", metadata: ["user.id": "\(request.userID)"])

        if let cart = try await cart(userID: request.userID) {
            return cart
        } else {
            // We decided to return empty cart in cases when user wasn't in the cache before
            return Oteldemo_Cart()
        }
    }

    func emptyCart(
        request: Oteldemo_EmptyCartRequest,
        context: ServerContext
    ) async throws -> Oteldemo_Empty {
        let useExperimentalAlgorithm = await openFeatureClient.value(
            for: "cartExperimentalClearing",
            defaultingTo: false
        )

        if useExperimentalAlgorithm {
            logger.info("Using experimental algorithm to clear cart.")
            throw UnimplementedError()
        }

        let emptyCartBytes: [UInt8] = try Oteldemo_Cart().serializedBytes()
        try await valkeyClient.hset(ValkeyKey(request.userID), data: [.init(field: "cart", value: emptyCartBytes)])
        try await valkeyClient.expire(ValkeyKey(request.userID), seconds: 60 * 60)

        return Oteldemo_Empty()
    }

    private func cart(userID: String) async throws -> Oteldemo_Cart? {
        try await withSpan("Cart") { span in
            span.attributes["user.id"] = userID

            guard let buffer = try await valkeyClient.hget(ValkeyKey(userID), field: "cart") else {
                return nil
            }
            return try Oteldemo_Cart(serializedBytes: Array(buffer.readableBytesView))
        }
    }

    struct UnimplementedError: Error {}
}
