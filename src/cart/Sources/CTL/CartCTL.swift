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

@main
struct CartCTL: AsyncParsableCommand {
    func run() async throws {
        let observability = try OTel.bootstrap()
        let port = ProcessInfo.processInfo.environment["CART_PORT"].flatMap(Int.init) ?? 8080

        guard let ofrepHost = ProcessInfo.processInfo.environment["FLAGD_HOST"],
              let ofrepPort = ProcessInfo.processInfo.environment["FLAGD_OFREP_PORT"] else {
            Self.exit()
        }
        let ofrepProvider = OFREPProvider(serverURL: URL(string: "http://\(ofrepHost):\(ofrepPort)")!)
        OpenFeatureSystem.setProvider(ofrepProvider)
        OpenFeatureSystem.addHooks([OpenFeatureTracingHook()])

        let service = CartService(openFeatureClient: OpenFeatureSystem.client())
        let server = GRPCServer(
            transport: .http2NIOPosix(
                address: .ipv4(host: "0.0.0.0", port: port),
                transportSecurity: .plaintext
            ),
            services: [service],
            interceptors: [ServerOTelTracingInterceptor(serverHostname: "0.0.0.0", networkTransportMethod: "tcp")]
        )

        let serviceGroup = ServiceGroup(
            services: [observability, ofrepProvider, server],
            gracefulShutdownSignals: [.sigint, .sigterm],
            logger: Logger(label: "cart")
        )

        try await serviceGroup.run()
    }
}

struct CartService: Oteldemo_CartService.SimpleServiceProtocol {
    let openFeatureClient: OpenFeatureClient

    func addItem(
        request: Oteldemo_AddItemRequest,
        context: ServerContext
    ) async throws -> Oteldemo_Empty {
        Oteldemo_Empty()
    }

    func getCart(
        request: Oteldemo_GetCartRequest,
        context: ServerContext
    ) async throws -> Oteldemo_Cart {
        var cart = Oteldemo_Cart()
        cart.userID = request.userID
        cart.items = [
            .with {
                $0.productID = "OLJCESPC7Z"
                $0.quantity = 1
            }
        ]
        return cart
    }

    func emptyCart(
        request: Oteldemo_EmptyCartRequest,
        context: ServerContext
    ) async throws -> Oteldemo_Empty {
        let mockCartFailure = await openFeatureClient.value(for: "cartFailure", defaultingTo: false)

        if mockCartFailure {
            try await Task.sleep(for: .seconds(5))
        }

        return Oteldemo_Empty()
    }
}
