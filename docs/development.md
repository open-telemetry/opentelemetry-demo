# Development

Development for this demo requires tooling in several programming languages.
Minimum required versions will be noted where possible, but it is recommended
to update to the latest version for all tooling. The OpenTelemetry demo team
will attempt to keep the services in this repository up to date with the latest
version for dependencies and tooling when possible.

## Generate Protobuf files

The `make generate-protobuf` command is provided to generate protobuf files for
all services. This can be used to compile code locally (without Docker) and
receive hints from IDEs such as IntelliJ or VS Code. It may be necessary to run
`npm install` within the frontend source folder before generating the files.

## Development tooling requirements

### .NET

- .NET 6.0+

### C++

- build-essential
- cmake
- libcurl4-openssl-dev
- libprotobuf-dev
- nlohmann-json3-dev
- pkg-config
- protobuf-compiler

### Elixir

- Erlang/OTP 23+
- Elixir 1.13+
- Rebar3 3.20+

### Go

- Go 1.19+
- protoc-gen-go
- protoc-gen-go-grpc

### Java

- JDK 17+
- Gradle 7+

### JavaScript

- Node.js 16+

### PHP

- PHP 8.1+
- Composer 2.4+

### Python

- Python 3.10
- grpcio-tools 1.48+

### Ruby

- Ruby 3.1+

### Rust

- Rust 1.61+
- protoc 3.21+
- protobuf-dev
