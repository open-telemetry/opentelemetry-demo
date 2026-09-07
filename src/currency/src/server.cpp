// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

#include <chrono>
#include <cerrno>
#include <csignal>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <math.h>
#include <pthread.h>
#include <demo.grpc.pb.h>
#include <grpc/health/v1/health.grpc.pb.h>

#include "opentelemetry/trace/context.h"
#include "opentelemetry/semconv/incubating/rpc_attributes.h"
#include "opentelemetry/trace/span_context_kv_iterable_view.h"
#include "opentelemetry/baggage/baggage.h"
#include "opentelemetry/nostd/string_view.h"
#include "opentelemetry/logs/event_id.h"
#include "logger_common.h"
#include "meter_common.h"
#include "tracer_common.h"

#include <grpcpp/grpcpp.h>
#include <grpcpp/server.h>
#include <grpcpp/server_builder.h>
#include <grpcpp/server_context.h>
#include <grpcpp/impl/codegen/string_ref.h>

using namespace std;
using namespace opentelemetry::baggage;
using namespace opentelemetry::trace;

using oteldemo::Empty;
using oteldemo::GetSupportedCurrenciesResponse;
using oteldemo::CurrencyConversionRequest;
using oteldemo::Money;

using grpc::Status;
using grpc::ServerContext;
using grpc::ServerBuilder;
using grpc::Server;

using Span            = Span;
using SpanContext     = SpanContext;
namespace context     = opentelemetry::context;
namespace metrics_api = opentelemetry::metrics;
namespace nostd       = opentelemetry::nostd;
namespace semconv     = opentelemetry::semconv;

using opentelemetry::logs::EventId;

namespace
{
  constexpr auto shutdown_timeout = std::chrono::seconds(9);
  constexpr auto server_shutdown_timeout = std::chrono::seconds(4);

  struct ServerShutdownResult
  {
    bool succeeded;
    std::chrono::steady_clock::time_point deadline;
  };

  ServerShutdownResult makeServerShutdownResult(bool succeeded)
  {
    return {succeeded, std::chrono::steady_clock::now() + shutdown_timeout};
  }

  std::chrono::microseconds remainingShutdownTimeout(
      std::chrono::steady_clock::time_point shutdown_deadline)
  {
    const auto remaining = std::chrono::duration_cast<std::chrono::microseconds>(
        shutdown_deadline - std::chrono::steady_clock::now());
    return remaining > std::chrono::microseconds::zero() ? remaining
                                                          : std::chrono::microseconds(1);
  }

  EventId eventName(nostd::string_view name) {
    // The OTLP exporter ignores the numeric EventId and exports only the event name.
    // Use 0 to satisfy the C++ API; revisit when the C++ SDK provides guidance.
    return EventId{0, name};
  }

  std::unordered_map<std::string, double> currency_conversion
  {
    {"EUR", 1.0},
    {"USD", 1.1305},
    {"JPY", 126.40},
    {"BGN", 1.9558},
    {"CZK", 25.592},
    {"DKK", 7.4609},
    {"GBP", 0.85970},
    {"HUF", 315.51},
    {"PLN", 4.2996},
    {"RON", 4.7463},
    {"SEK", 10.5375},
    {"CHF", 1.1360},
    {"ISK", 136.80},
    {"NOK", 9.8040},
    {"HRK", 7.4210},
    {"RUB", 74.4208},
    {"TRY", 6.1247},
    {"AUD", 1.6072},
    {"BRL", 4.2682},
    {"CAD", 1.5128},
    {"CNY", 7.5857},
    {"HKD", 8.8743},
    {"IDR", 15999.40},
    {"ILS", 4.0875},
    {"INR", 79.4320},
    {"KRW", 1275.05},
    {"MXN", 21.7999},
    {"MYR", 4.6289},
    {"NZD", 1.6679},
    {"PHP", 59.083},
    {"SGD", 1.5349},
    {"THB", 36.012},
    {"ZAR", 16.0583},
  };

  const char* version_env = std::getenv("VERSION");
  std::string version = version_env != nullptr ? version_env : "unknown";
  std::string name{ "currency" };

  nostd::unique_ptr<metrics_api::Counter<uint64_t>> currency_counter;
  nostd::shared_ptr<opentelemetry::logs::Logger> logger;

class HealthServer final : public grpc::health::v1::Health::Service
{
  Status Check(
    ServerContext* context,
    const grpc::health::v1::HealthCheckRequest* request,
    grpc::health::v1::HealthCheckResponse* response) override
  {
    response->set_status(grpc::health::v1::HealthCheckResponse::SERVING);
    return Status::OK;
  }
};

class CurrencyService final : public oteldemo::CurrencyService::Service
{
  Status GetSupportedCurrencies(ServerContext* context,
  	const Empty* request,
  	GetSupportedCurrenciesResponse* response) override
  {
    StartSpanOptions options;
    options.kind = SpanKind::kServer;
    GrpcServerCarrier carrier(context);

    auto prop        = context::propagation::GlobalTextMapPropagator::GetGlobalPropagator();
    auto current_ctx = context::RuntimeContext::GetCurrent();
    auto new_context = prop->Extract(carrier, current_ctx);
    options.parent   = GetSpan(new_context)->GetContext();

    std::string span_name = "Currency/GetSupportedCurrencies";
    auto span =
        get_tracer("currency")->StartSpan(span_name,
                                      {{semconv::rpc::kRpcSystem, "grpc"},
                                       {semconv::rpc::kRpcService, "oteldemo.CurrencyService"},
                                       {semconv::rpc::kRpcMethod, "GetSupportedCurrencies"},
                                       {semconv::rpc::kRpcGrpcStatusCode, semconv::rpc::RpcGrpcStatusCodeValues::kOk}},
                                      options);
    auto scope = get_tracer("currency")->WithActiveSpan(span);

    span->AddEvent("Processing supported currencies request");

    for (auto &code : currency_conversion) {
      response->add_currency_codes(code.first);
    }

    span->AddEvent("Currencies fetched, response sent back");
    span->SetStatus(StatusCode::kOk);

    logger->Info(eventName("currency.get_supported_currencies"), "GetSupportedCurrencies successful");

    // Make sure to end your spans!
    span->End();
  	return Status::OK;
  }

  double getDouble(Money& money) {
    auto units = money.units();
    auto nanos = money.nanos();

    double decimal = 0.0;
    while (nanos != 0) {
      double t = (double)(nanos%10)/10;
      nanos = nanos/10;
      decimal = decimal/10 + t;
    }

    return double(units) + decimal;
  }

  void getUnitsAndNanos(Money& money, double value) {
    long unit = (long)value;
    double rem = value - unit;
    long nano = rem * pow(10, 9);
    money.set_units(unit);
    money.set_nanos(nano);
  }

  Status Convert(ServerContext* context,
  	const CurrencyConversionRequest* request,
  	Money* response) override
  {
    StartSpanOptions options;
    options.kind = SpanKind::kServer;
    GrpcServerCarrier carrier(context);

    auto prop        = context::propagation::GlobalTextMapPropagator::GetGlobalPropagator();
    auto current_ctx = context::RuntimeContext::GetCurrent();
    auto new_context = prop->Extract(carrier, current_ctx);
    options.parent   = GetSpan(new_context)->GetContext();

    std::string span_name = "Currency/Convert";
    auto span =
        get_tracer("currency")->StartSpan(span_name,
                                      {{semconv::rpc::kRpcSystem, "grpc"},
                                       {semconv::rpc::kRpcService, "oteldemo.CurrencyService"},
                                       {semconv::rpc::kRpcMethod, "Convert"},
                                       {semconv::rpc::kRpcGrpcStatusCode, semconv::rpc::RpcGrpcStatusCodeValues::kOk}},
                                      options);
    auto scope = get_tracer("currency")->WithActiveSpan(span);

    span->AddEvent("Processing currency conversion request");

    try {
      // Do the conversion work
      Money from = request->from();
      string from_code = from.currency_code();
      double rate = currency_conversion[from_code];
      double one_euro = getDouble(from) / rate ;

      string to_code = request->to_code();
      double to_rate = currency_conversion[to_code];

      double final = one_euro * to_rate;
      getUnitsAndNanos(*response, final);
      response->set_currency_code(to_code);

      span->SetAttribute("demo.exchange.from", from_code);
      span->SetAttribute("demo.exchange.to", to_code);

      CurrencyCounter(to_code);

      span->AddEvent("Conversion successful, response sent back");
      span->SetStatus(StatusCode::kOk);

      logger->Info(eventName("currency.conversion"),
                   "conversion successful",
                   opentelemetry::common::MakeAttributes(
                       {{"currency.from", from_code.c_str()},
                        {"currency.to", to_code.c_str()}}));
      
      // End the span
      span->End();
      return Status::OK;

    } catch(...) {
      span->AddEvent("Conversion failed");
      span->SetStatus(StatusCode::kError);

      logger->Error(eventName("currency.conversion_failed"), "conversion failure");

      span->End();
      return Status::CANCELLED;
    }
    return Status::OK;
  }

  void CurrencyCounter(const std::string& to_code)
  {
      std::map<std::string, std::string> labels = { {"demo.exchange.to", to_code} };
      auto labelkv = common::KeyValueIterableView<decltype(labels)>{ labels };
      currency_counter->Add(1, labelkv);
  }
};

ServerShutdownResult RunServer(uint16_t port, const sigset_t& shutdown_signals)
{
  std::string ip("0.0.0.0");

  const char* ipv6_enabled = std::getenv("IPV6_ENABLED");

  if (ipv6_enabled != nullptr && std::string(ipv6_enabled) == "true") {
    ip = "[::]";
    logger->Info(eventName("currency.server.ip_overwrite"),
                 "Overwriting Localhost IP",
                 opentelemetry::common::MakeAttributes({{"server.address", ip.c_str()}}));
  }

  std::string address(ip + ":" +  std::to_string(port));

  CurrencyService currencyService;
  HealthServer healthService;
  ServerBuilder builder;

  builder.RegisterService(&currencyService);
  builder.RegisterService(&healthService);
  builder.AddListeningPort(address, grpc::InsecureServerCredentials());

  std::unique_ptr<Server> server(builder.BuildAndStart());
  if (server == nullptr) {
    std::cerr << "Failed to start Currency Server\n";
    return makeServerShutdownResult(false);
  }

  logger->Info(eventName("currency.server.started"),
               "Currency Server started",
               opentelemetry::common::MakeAttributes({{"server.address", address.c_str()}}));

  int received_signal = 0;
  const int signal_error = sigwait(&shutdown_signals, &received_signal);
  if (signal_error != 0) {
    std::cerr << "Failed to wait for shutdown signal: " << std::strerror(signal_error) << "\n";
  } else {
    const char* signal_name = received_signal == SIGTERM ? "SIGTERM" : "SIGINT";
    const std::string shutdown_message =
        std::string("Received ") + signal_name + ", shutting down Currency Server";
    std::cout << shutdown_message << "\n";
    logger->Info(eventName("currency.server.stopping"), shutdown_message);
  }

  const auto result = makeServerShutdownResult(signal_error == 0);
  server->Shutdown(std::chrono::system_clock::now() + server_shutdown_timeout);
  server->Wait();
  return result;
}
}

int main(int argc, char **argv) {

  sigset_t shutdown_signals;
  if (sigemptyset(&shutdown_signals) == -1 ||
      sigaddset(&shutdown_signals, SIGINT) == -1 ||
      sigaddset(&shutdown_signals, SIGTERM) == -1) {
    std::cerr << "Failed to configure shutdown signals: " << std::strerror(errno) << "\n";
    return 1;
  }

  const int signal_mask_error = pthread_sigmask(SIG_BLOCK, &shutdown_signals, nullptr);
  if (signal_mask_error != 0) {
    std::cerr << "Failed to block shutdown signals: " << std::strerror(signal_mask_error) << "\n";
    return 1;
  }

  if (argc < 2) {
    std::cout << "Usage: currency <port>";
    return 0;
  }

  uint16_t port = atoi(argv[1]);

  auto tracer_provider = initTracer();
  auto meter_provider = initMeter();
  auto logger_provider = initLogger();
  currency_counter = initIntCounter("demo.exchange.conversions", version);
  logger = getLogger(name);

  const auto server_shutdown = RunServer(port, shutdown_signals);
  const bool tracer_shutdown =
      tracer_provider->Shutdown(remainingShutdownTimeout(server_shutdown.deadline));
  if (!tracer_shutdown) {
    std::cerr << "Tracer provider shutdown failed\n";
  }

  const bool meter_flush =
      meter_provider->ForceFlush(remainingShutdownTimeout(server_shutdown.deadline));
  if (!meter_flush) {
    std::cerr << "Meter provider flush failed\n";
  }

  const bool meter_shutdown =
      meter_provider->Shutdown(remainingShutdownTimeout(server_shutdown.deadline));
  if (!meter_shutdown) {
    std::cerr << "Meter provider shutdown failed\n";
  }

  const bool logger_shutdown =
      logger_provider->Shutdown(remainingShutdownTimeout(server_shutdown.deadline));
  if (!logger_shutdown) {
    std::cerr << "Logger provider shutdown failed\n";
  }

  return server_shutdown.succeeded ? 0 : 1;
}
