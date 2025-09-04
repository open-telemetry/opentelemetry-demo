import ArgumentParser
import Foundation
import Logging
import GRPCCore
import GRPCNIOTransportHTTP2
import ServiceLifecycle
import GRPCServiceLifecycle

@main
struct CartCTL: AsyncParsableCommand {
    func run() async throws {
        let port = ProcessInfo.processInfo.environment["CART_PORT"].flatMap(Int.init) ?? 8080

        let service = CartService()
        let server = GRPCServer(
            transport: .http2NIOPosix(
                address: .ipv4(host: "0.0.0.0", port: port),
                transportSecurity: .plaintext
            ),
            services: [service]
        )

        let serviceGroup = ServiceGroup(
            services: [server],
            gracefulShutdownSignals: [.sigint, .sigterm],
            logger: Logger(label: "cart")
        )

        try await serviceGroup.run()
    }
}

struct CartService: Oteldemo_CartService.SimpleServiceProtocol {
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
        Oteldemo_Empty()
    }
}
