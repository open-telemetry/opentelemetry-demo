// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

#include <iostream>
#include <math.h>
#include <demo.grpc.pb.h>
#include <grpc/health/v1/health.grpc.pb.h>

#include "opentelemetry/trace/context.h"
#include "opentelemetry/trace/semantic_conventions.h"
#include "opentelemetry/trace/span_context_kv_iterable_view.h"
#include "opentelemetry/baggage/baggage.h"
#include "opentelemetry/nostd/string_view.h"
#include "tracer_common.h"

#include <grpcpp/grpcpp.h>
#include <grpcpp/server.h>
#include <grpcpp/server_builder.h>
#include <grpcpp/server_context.h>
#include <grpcpp/impl/codegen/string_ref.h>

using namespace std;

using hipstershop::Empty;
using hipstershop::GetSupportedCurrenciesResponse;
using hipstershop::CurrencyConversionRequest;
using hipstershop::Money;

using grpc::Status;
using grpc::ServerContext;
using grpc::ServerBuilder;
using grpc::Server;

using Span        = opentelemetry::trace::Span;
using SpanContext = opentelemetry::trace::SpanContext;
using namespace opentelemetry::trace;
using namespace opentelemetry::baggage;
namespace context = opentelemetry::context;

namespace
{
  std::unordered_map<std::string, double> currency_conversion{
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

class CurrencyService final : public hipstershop::CurrencyService::Service
{
  Status GetSupportedCurrencies(ServerContext* context,
  	const Empty* request,
  	GetSupportedCurrenciesResponse* response) override
  {
    // Read baggage from client context
    auto clientContext = context->client_metadata();
    auto range = clientContext.equal_range("baggage");
    std::vector<std::string> baggageLists;
    for (auto i = range.first; i != range.second; ++i)
    {
      baggageLists.emplace_back(std::string(i->second.data()));
    }
    std::vector<opentelemetry::nostd::shared_ptr<Baggage>> baggages(baggageLists.size());
    for (int i = 0; i < baggageLists.size(); i++) {
      auto baggage = Baggage::FromHeader(baggageLists[i]);
      baggages[i] = baggage;
    }

    StartSpanOptions options;
    options.kind = SpanKind::kServer;
    GrpcServerCarrier carrier(context);

    auto prop        = context::propagation::GlobalTextMapPropagator::GetGlobalPropagator();
    auto current_ctx = context::RuntimeContext::GetCurrent();
    auto new_context = prop->Extract(carrier, current_ctx);
    options.parent   = GetSpan(new_context)->GetContext();

    std::string span_name = "CurrencyService/GetSupportedCurrencies";
    auto span =
        get_tracer("currencyservice")->StartSpan(span_name,
                                      {{SemanticConventions::RPC_SYSTEM, "grpc"},
                                       {SemanticConventions::RPC_SERVICE, "CurrencyService"},
                                       {SemanticConventions::RPC_METHOD, "GetSupportedCurrencies"},
                                       {SemanticConventions::RPC_GRPC_STATUS_CODE, 0}},
                                      options);
    auto scope = get_tracer("currencyservice")->WithActiveSpan(span);

    for (auto& baggage : baggages) {
      // Set the key value pairs from baggage to Span Attributes
      baggage->GetAllEntries([&span](opentelemetry::nostd::string_view key,
          opentelemetry::nostd::string_view value) {
        span->SetAttribute(key, value);
        return true;
      });
    }

    // Fetch and parse whatever HTTP headers we can from the gRPC request.
    span->AddEvent("Processing supported currencies request");

    for (auto &code : currency_conversion) {
      response->add_currency_codes(code.first);
    }

    span->AddEvent("Currencies fetched, response sent back");
    span->SetStatus(StatusCode::kOk);
    // Make sure to end your spans!
    span->End();

    std::cout << __func__ << " successful" << std::endl;
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
    // Read baggage from client context
    auto clientContext = context->client_metadata();
    auto range = clientContext.equal_range("baggage");
    std::vector<std::string> baggageLists;
    for (auto i = range.first; i != range.second; ++i)
    {
      baggageLists.emplace_back(std::string(i->second.data()));
    }
    std::vector<opentelemetry::nostd::shared_ptr<Baggage>> baggages(baggageLists.size());
    for (int i = 0; i < baggageLists.size(); i++) {
      auto baggage = Baggage::FromHeader(baggageLists[i]);
      baggages[i] = baggage;
    }

    StartSpanOptions options;
    options.kind = SpanKind::kServer;
    GrpcServerCarrier carrier(context);

    auto prop        = context::propagation::GlobalTextMapPropagator::GetGlobalPropagator();
    auto current_ctx = context::RuntimeContext::GetCurrent();
    auto new_context = prop->Extract(carrier, current_ctx);
    options.parent   = GetSpan(new_context)->GetContext();

    std::string span_name = "CurrencyService/Convert";
    auto span =
        get_tracer("currencyservice")->StartSpan(span_name,
                                      {{SemanticConventions::RPC_SYSTEM, "grpc"},
                                       {SemanticConventions::RPC_SERVICE, "CurrencyService"},
                                       {SemanticConventions::RPC_METHOD, "Convert"},
                                       {SemanticConventions::RPC_GRPC_STATUS_CODE, 0}},
                                      options);
    auto scope = get_tracer("currencyservice")->WithActiveSpan(span);

    for (auto& baggage : baggages) {
      // Set the key value pairs from baggage to Span Attributes
      baggage->GetAllEntries([&span](opentelemetry::nostd::string_view key,
          opentelemetry::nostd::string_view value) {
        span->SetAttribute(key, value);
        return true;
      });
    }
    // Fetch and parse whatever HTTP headers we can from the gRPC request.
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

      span->SetAttribute("app.currency.conversion.from", from_code);
      span->SetAttribute("app.currency.conversion.to", to_code);

      // End the span
      span->AddEvent("Conversion successful, response sent back");
      span->SetStatus(StatusCode::kOk);
      std::cout << __func__ << " conversion successful" << std::endl;
      span->End();
      return Status::OK;

    } catch(...) {
      span->AddEvent("Conversion failed");
      span->SetStatus(StatusCode::kError);
      std::cout << __func__ << " conversion failure" << std::endl;
      span->End();
      return Status::CANCELLED;
    }
    return Status::OK;
  }
};

void RunServer(uint16_t port)
{
  std::string address("0.0.0.0:" + std::to_string(port));
  CurrencyService currencyService;
  HealthServer healthService;
  ServerBuilder builder;

  builder.RegisterService(&currencyService);
  builder.RegisterService(&healthService);
  builder.AddListeningPort(address, grpc::InsecureServerCredentials());

  std::unique_ptr<Server> server(builder.BuildAndStart());
  std::cout << "Currency Server listening on port: " << address << std::endl;
  server->Wait();
  server->Shutdown();
}
}

int main(int argc, char **argv) {

  if (argc < 2) {
    std::cout << "Usage: currencyservice <port>";
    return 0;
  }

  uint16_t port = atoi(argv[1]);

  std::cout << "Port: " << port << "\n";

  initTracer();
  RunServer(port);

  return 0;
}
