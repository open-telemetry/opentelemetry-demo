const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});

    const otel = b.dependency("opentelemetry", .{
        .target = target,
    });

    const exe = b.addExecutable(.{
        .name = "inventory",
        .root_module = b.createModule(.{
            .root_source_file = b.path("src/main.zig"),
            .target = target,
            .optimize = optimize,
            .imports = &.{
                .{ .name = "opentelemetry-sdk", .module = otel.module("sdk") },
                .{ .name = "opentelemetry-semconv", .module = otel.module("opentelemetry-semconv") },
            },
        }),
    });

    b.installArtifact(exe);

    const run_cmd = b.addRunArtifact(exe);
    run_cmd.step.dependOn(b.getInstallStep());
    const run_step = b.step("run", "Run the inventory service");
    run_step.dependOn(&run_cmd.step);

    const tests = b.addTest(.{
        .root_module = exe.root_module,
    });
    const test_step = b.step("test", "Run unit tests");
    test_step.dependOn(&b.addRunArtifact(tests).step);
}
