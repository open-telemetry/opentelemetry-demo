# Development

Development for this demo requires tooling in several different languages.
Minimum required versions will be noted where possible, but it is recommended
to update to the latest version for all tooling. The OpenTelemetry demo team
will attempt the services in this repository upto date with the latest version 
for dependencies and tooling when possible.

## Generate Protobuf files

The `make generate-protobuf` command is provided to generate protobuf files for
all services. This can be used to compile code locally (without docker) and
receive hints from IDEs such as IntelliJ or VS code.

## Development tooling requirements

### .NET

- .NET Core runtime 6+

### C++

- build-essential
- pkg-config
- protobuf-compiler
- libprotobuf-dev
- libcurl4-openssl-dev
- nlohmann-json3-dev
- cmake

### Elixir

- Erlang/OTP 23+
- Elixir 1.13+
- Rebar3 3.20+

### Go

- Go 1.19+
- protoc 3.21+

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
