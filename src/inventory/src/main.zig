const std = @import("std");
const sdk = @import("opentelemetry-sdk");
const semconv = @import("opentelemetry-semconv");

const trace_api = sdk.api.trace;
const context_api = sdk.api.context;
const metrics_sdk = sdk.metrics;
const Attribute = sdk.Attribute;

const initial_stock: i64 = 100;

var listener_handle = std.atomic.Value(std.posix.fd_t).init(-1);
const max_body_bytes = 64 * 1024;

const ReserveRequest = struct {
    order_id: []const u8,
    items: []const Item,

    const Item = struct {
        product_id: []const u8,
        quantity: u32,
    };
};

const Telemetry = struct {
    tracer: *trace_api.Tracer,
    propagator: *sdk.propagation.CompositePropagator,
    reservations: *metrics_sdk.Counter(u64),
    stock_level: *metrics_sdk.Gauge(i64),
};

const Stock = struct {
    allocator: std.mem.Allocator,
    levels: std.StringHashMapUnmanaged(i64) = .empty,

    const Reservation = struct {
        product_id: []const u8,
        level: i64,
    };

    fn deinit(self: *Stock) void {
        var keys = self.levels.keyIterator();
        while (keys.next()) |key| self.allocator.free(key.*);
        self.levels.deinit(self.allocator);
    }

    fn reserve(self: *Stock, product_id: []const u8, quantity: u32) !Reservation {
        const entry = try self.levels.getOrPut(self.allocator, product_id);
        if (!entry.found_existing) {
            entry.key_ptr.* = self.allocator.dupe(u8, product_id) catch |err| {
                self.levels.removeByPtr(entry.key_ptr);
                return err;
            };
            entry.value_ptr.* = initial_stock;
        }
        if (entry.value_ptr.* < quantity) {
            entry.value_ptr.* = @max(initial_stock, quantity);
        }
        entry.value_ptr.* -= quantity;
        return .{ .product_id = entry.key_ptr.*, .level = entry.value_ptr.* };
    }
};

const FeatureFlags = struct {
    client: std.http.Client,
    url: ?[]const u8,

    fn init(allocator: std.mem.Allocator, io: std.Io, environ: *const std.process.Environ.Map) !FeatureFlags {
        const host = environ.get("FLAGD_HOST");
        const port = environ.get("FLAGD_OFREP_PORT");
        const url = if (host != null and port != null)
            try std.fmt.allocPrint(
                allocator,
                "http://{s}:{s}/ofrep/v1/evaluate/flags/inventoryFailure",
                .{ host.?, port.? },
            )
        else
            null;
        return .{
            .client = .{ .allocator = allocator, .io = io },
            .url = url,
        };
    }

    fn deinit(self: *FeatureFlags) void {
        if (self.url) |url| self.client.allocator.free(url);
        self.client.deinit();
    }

    fn inventoryFailure(self: *FeatureFlags, allocator: std.mem.Allocator, product_id: []const u8) bool {
        const url = self.url orelse return false;
        return self.evaluate(allocator, url, product_id) catch |err| {
            std.log.warn("inventoryFailure evaluation failed: {s}", .{@errorName(err)});
            return false;
        };
    }

    fn evaluate(self: *FeatureFlags, allocator: std.mem.Allocator, url: []const u8, product_id: []const u8) !bool {
        const payload = try std.json.Stringify.valueAlloc(allocator, .{
            .context = .{ .product_id = product_id },
        }, .{});
        defer allocator.free(payload);

        var response: std.Io.Writer.Allocating = .init(allocator);
        defer response.deinit();

        const result = try self.client.fetch(.{
            .location = .{ .url = url },
            .method = .POST,
            .payload = payload,
            .headers = .{ .content_type = .{ .override = "application/json" } },
            .response_writer = &response.writer,
        });
        if (result.status != .ok) return false;

        const parsed = try std.json.parseFromSlice(
            struct { value: bool = false },
            allocator,
            response.written(),
            .{ .ignore_unknown_fields = true },
        );
        defer parsed.deinit();
        return parsed.value.value;
    }
};

const Response = struct {
    status: std.http.Status,
    body: []const u8,
    error_description: ?[]const u8 = null,
};

const Handler = struct {
    allocator: std.mem.Allocator,
    telemetry: *Telemetry,
    stock: *Stock,
    flags: *FeatureFlags,

    fn reserve(self: *Handler, arena: std.mem.Allocator, request: *std.http.Server.Request, span: *trace_api.Span) !Response {
        if (request.head.method != .POST) {
            return .{ .status = .method_not_allowed, .body = "{\"error\":\"method not allowed\"}", .error_description = "method not allowed" };
        }
        if (missingBodyLength(request.head)) {
            return .{ .status = .length_required, .body = "{\"error\":\"length required\"}", .error_description = "missing content-length" };
        }

        var body_buffer: [1024]u8 = undefined;
        const body_reader = request.readerExpectNone(&body_buffer);
        const body = body_reader.allocRemaining(arena, .limited(max_body_bytes)) catch {
            return .{ .status = .bad_request, .body = "{\"error\":\"unreadable body\"}", .error_description = "unreadable body" };
        };

        const order = std.json.parseFromSliceLeaky(ReserveRequest, arena, body, .{
            .ignore_unknown_fields = true,
        }) catch {
            return .{ .status = .bad_request, .body = "{\"error\":\"invalid body\"}", .error_description = "invalid body" };
        };

        try span.setAttribute("demo.order.id", .{ .string = order.order_id });
        try span.setAttribute("demo.order.items.count", .{ .int = @intCast(order.items.len) });

        for (order.items) |item| {
            if (self.flags.inventoryFailure(self.allocator, item.product_id)) {
                try span.setAttribute("demo.product.id", .{ .string = item.product_id });
                try self.telemetry.reservations.add(1, .{ "demo.inventory.reservation.status", @as([]const u8, "rejected") });
                span.setStatus(trace_api.Status.error_with_description("inventoryFailure flag enabled"));
                return .{ .status = .service_unavailable, .body = "{\"error\":\"inventory unavailable\"}" };
            }
        }

        for (order.items) |item| {
            const reservation = try self.stock.reserve(item.product_id, item.quantity);
            try self.telemetry.stock_level.record(reservation.level, .{ "demo.product.id", reservation.product_id });
            try span.addEvent("reserved", null, &[_]Attribute{
                .{ .key = "demo.product.id", .value = .{ .string = reservation.product_id } },
                .{ .key = "demo.product.quantity", .value = .{ .int = item.quantity } },
            });
        }
        try self.telemetry.reservations.add(1, .{ "demo.inventory.reservation.status", @as([]const u8, "reserved") });

        return .{ .status = .ok, .body = "{\"status\":\"reserved\"}" };
    }
};

pub fn main(init: std.process.Init) !void {
    const allocator = init.gpa;
    const io = init.io;

    const port = try portFromEnv(init.environ_map);

    var cfg = try sdk.config.init(allocator, io, init.environ_map);
    defer cfg.deinit();
    sdk.config.set(cfg);

    var propagator = try sdk.propagation.createGlobalPropagator(allocator, io, init.environ_map);
    defer propagator.deinit();

    var otlp_config = try sdk.otlp.ConfigOptions.init(allocator, init.environ_map);
    defer otlp_config.deinit();

    var exporter = try sdk.trace.OTLPExporter.init(allocator, io, otlp_config);
    defer exporter.deinit();

    var seed: u64 = undefined;
    io.random(std.mem.asBytes(&seed));
    var prng = std.Random.DefaultPrng.init(seed);

    var provider = try sdk.trace.TracerProvider.init(allocator, io, .{
        .Random = sdk.trace.RandomIDGenerator.init(prng.random()),
    });
    defer provider.deinit();

    var processor = sdk.trace.SimpleProcessor.init(allocator, io, exporter.asSpanExporter());
    try provider.addSpanProcessor(processor.asSpanProcessor());

    const tracer = try provider.getTracer(.{
        .name = "inventory.api",
        .version = "0.1.0",
        .schema_url = semconv.SCHEMA_URL,
    });

    const meter_provider = try metrics_sdk.MeterProvider.init(allocator, io);
    defer meter_provider.shutdown();

    const metric_exporter = try metrics_sdk.MetricExporter.OTLP(allocator, io, null, null, otlp_config);
    defer metric_exporter.otlp.deinit();

    const metric_reader = try metrics_sdk.PeriodicExportingReader.init(
        allocator,
        io,
        meter_provider,
        metric_exporter.exporter,
        cfg.metrics_config.export_interval_ms,
        null,
    );
    defer metric_reader.shutdown();

    const meter = try meter_provider.getMeter(.{
        .name = "inventory.api",
        .version = "0.1.0",
        .schema_url = semconv.SCHEMA_URL,
    });

    var telemetry = Telemetry{
        .tracer = tracer,
        .propagator = &propagator,
        .reservations = try meter.createCounter(u64, .{
            .name = "demo.inventory.reservations",
            .description = "Number of order reservations processed",
            .unit = "{reservation}",
        }),
        .stock_level = try meter.createGauge(i64, .{
            .name = "demo.inventory.stock.level",
            .description = "Units in stock per product after the last reservation",
            .unit = "{unit}",
        }),
    };

    var stock = Stock{ .allocator = allocator };
    defer stock.deinit();

    var flags = try FeatureFlags.init(allocator, io, init.environ_map);
    defer flags.deinit();

    var handler = Handler{
        .allocator = allocator,
        .telemetry = &telemetry,
        .stock = &stock,
        .flags = &flags,
    };

    var address = std.Io.net.IpAddress.parseIp4("0.0.0.0", port) catch unreachable;
    var listener = try address.listen(io, .{ .reuse_address = true });
    defer listener.deinit(io);

    listener_handle.store(listener.socket.handle, .release);
    installTerminationHandler();

    std.log.info("inventory listening on port {d}", .{port});

    while (true) {
        const stream = listener.accept(io) catch |err| switch (err) {
            error.SocketNotListening => break,
            else => {
                std.log.err("accept failed: {s}", .{@errorName(err)});
                continue;
            },
        };
        defer stream.close(io);

        handleConnection(&handler, io, stream) catch |err| {
            std.log.err("connection failed: {s}", .{@errorName(err)});
        };
    }
    std.log.info("inventory shutting down", .{});
}

fn installTerminationHandler() void {
    const action: std.posix.Sigaction = .{
        .handler = .{ .handler = handleTermination },
        .mask = std.posix.sigemptyset(),
        .flags = 0,
    };
    std.posix.sigaction(.TERM, &action, null);
    std.posix.sigaction(.INT, &action, null);
}

fn handleTermination(_: std.posix.SIG) callconv(.c) void {
    const handle = listener_handle.load(.acquire);
    if (handle >= 0) _ = std.posix.system.shutdown(handle, std.posix.SHUT.RD);
}

fn handleConnection(handler: *Handler, io: std.Io, stream: std.Io.net.Stream) !void {
    var read_buffer: [8192]u8 = undefined;
    var write_buffer: [8192]u8 = undefined;

    var stream_reader = stream.reader(io, &read_buffer);
    var stream_writer = stream.writer(io, &write_buffer);

    var http_server = std.http.Server.init(&stream_reader.interface, &stream_writer.interface);

    var request = http_server.receiveHead() catch return;

    const route = routeOf(request.head.target);

    if (route.kind == .health) {
        try request.respond("{\"status\":\"ok\"}", .{
            .keep_alive = false,
            .extra_headers = &.{
                .{ .name = "content-type", .value = "application/json" },
            },
        });
        return;
    }

    var arena_state = std.heap.ArenaAllocator.init(handler.allocator);
    defer arena_state.deinit();
    const arena = arena_state.allocator();

    const parent_context = try parentContextFrom(handler, &request);
    defer if (parent_context) |ctx| {
        var owned = ctx;
        trace_api.freeSerializedSpanContext(handler.allocator, owned);
        owned.deinit();
    };

    var span = try handler.telemetry.tracer.startSpan(handler.allocator, route.span_name, .{
        .kind = .Server,
        .parent_context = parent_context,
    });
    defer span.deinit();

    try span.setAttribute(semconv.attribute.http_request_method.base.name, .{
        .string = @tagName(request.head.method),
    });
    if (route.kind != .unknown) {
        try span.setAttribute(semconv.attribute.http_route.name, .{ .string = route.path });
    }

    const response: Response = switch (route.kind) {
        .reserve => try handler.reserve(arena, &request, &span),
        .health => unreachable,
        .unknown => .{ .status = .not_found, .body = "{\"error\":\"not found\"}", .error_description = "unknown route" },
    };

    try span.setAttribute(
        semconv.attribute.http_response_status_code.name,
        .{ .int = @intFromEnum(response.status) },
    );
    if (response.error_description) |description| {
        span.setStatus(trace_api.Status.error_with_description(description));
    }

    span.end(null);

    try request.respond(response.body, .{
        .status = response.status,
        .keep_alive = false,
        .extra_headers = &.{
            .{ .name = "content-type", .value = "application/json" },
        },
    });
}

fn parentContextFrom(handler: *Handler, request: *const std.http.Server.Request) !?context_api.Context {
    var headers = std.StringHashMap([]const u8).init(handler.allocator);
    defer headers.deinit();

    var it = request.iterateHeaders();
    while (it.next()) |header| {
        try headers.put(header.name, header.value);
    }

    var remote = (try handler.telemetry.propagator.extractTraceContext(&headers)) orelse return null;
    defer remote.trace_state.deinit();

    return try trace_api.insertSpanContext(handler.allocator, remote);
}

fn missingBodyLength(head: std.http.Server.Request.Head) bool {
    if (!head.method.requestHasBody()) return false;
    return head.transfer_encoding == .none and head.content_length == null;
}

const Route = struct {
    kind: enum { reserve, health, unknown },
    path: []const u8,
    span_name: []const u8,
};

fn routeOf(target: []const u8) Route {
    const path = std.mem.sliceTo(target, '?');

    if (std.mem.eql(u8, path, "/reserve")) {
        return .{ .kind = .reserve, .path = "/reserve", .span_name = "POST /reserve" };
    }
    if (std.mem.eql(u8, path, "/health")) {
        return .{ .kind = .health, .path = "/health", .span_name = "GET /health" };
    }
    return .{ .kind = .unknown, .path = path, .span_name = "HTTP" };
}

fn portFromEnv(environ: *const std.process.Environ.Map) !u16 {
    const raw = environ.get("INVENTORY_PORT") orelse return error.MissingInventoryPort;
    return std.fmt.parseInt(u16, raw, 10);
}

test "routeOf strips the query string" {
    const route = routeOf("/reserve?sku=OLJCESPC7Z");
    try std.testing.expectEqual(.reserve, route.kind);
    try std.testing.expectEqualStrings("/reserve", route.path);
}

test "routeOf reports unknown paths" {
    const route = routeOf("/nope");
    try std.testing.expectEqual(.unknown, route.kind);
}

test "Stock seeds unknown products and decrements" {
    var stock = Stock{ .allocator = std.testing.allocator };
    defer stock.deinit();

    const first = try stock.reserve("OLJCESPC7Z", 3);
    try std.testing.expectEqual(initial_stock - 3, first.level);

    const second = try stock.reserve("OLJCESPC7Z", 2);
    try std.testing.expectEqual(initial_stock - 5, second.level);
}

test "Stock restocks when a reservation would go below zero" {
    var stock = Stock{ .allocator = std.testing.allocator };
    defer stock.deinit();

    _ = try stock.reserve("66VCHSJNUP", 99);
    const restocked = try stock.reserve("66VCHSJNUP", 5);
    try std.testing.expectEqual(initial_stock - 5, restocked.level);

    const oversized = try stock.reserve("66VCHSJNUP", 250);
    try std.testing.expectEqual(0, oversized.level);
}
