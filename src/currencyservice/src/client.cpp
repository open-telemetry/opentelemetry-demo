// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

#include <iostream>
#include <time.h>
#include <chrono>
#include <thread>
#include <demo.grpc.pb.h>
#include <grpc/health/v1/health.grpc.pb.h>

#include <grpcpp/grpcpp.h>
#include <grpcpp/server.h>
#include <grpcpp/server_builder.h>
#include <grpcpp/server_context.h>

using namespace std;

using hipstershop::CurrencyService;
using hipstershop::Empty;
using hipstershop::GetSupportedCurrenciesResponse;
using hipstershop::CurrencyConversionRequest;
using hipstershop::Money;

using grpc::Status;
using grpc::ServerContext;
using grpc::ServerBuilder;
using grpc::Server;
using grpc::Channel;
using grpc::StubOptions;
using grpc::ClientContext;
using grpc::health::v1::Health;
using grpc::health::v1::HealthCheckRequest;
using grpc::health::v1::HealthCheckResponse;

namespace
{
class CurrencyClient
{
public:
  CurrencyClient(std::shared_ptr<Channel> channel)
  : stub_(CurrencyService::NewStub(channel, StubOptions{}))
  , hc_stub_(grpc::health::v1::Health::NewStub(channel)) {}

  void GetSupportedCurrencies()
  {
    Empty request;
    GetSupportedCurrenciesResponse response;
    ClientContext context;

    supported_currencies.clear();
    Status status = stub_->GetSupportedCurrencies(&context, request, &response);

    std::cout << "Supported Currencies are: \n[ ";
    for (int i = 0; i < response.currency_codes_size(); i++) {
      std::cout << response.currency_codes(i) << " ";
      supported_currencies.push_back(response.currency_codes(i));
    }
    std::cout << "]" << std::endl;
  }

  void Convert()
  {
    size_t max = supported_currencies.size();
    srand(time(0));
    uint32_t src_index = rand()%max;
    uint32_t dst_index = rand()%max;
    uint32_t unit = rand()%100;
    uint32_t nano = rand()%100;

    CurrencyConversionRequest request;
    Money *money = request.mutable_from();
    money->set_currency_code(supported_currencies[src_index]);
    money->set_units(unit);
    money->set_nanos(nano);
    request.set_to_code(supported_currencies[dst_index]);

    std::cout << "Sending conversion request to convert from "
      << unit << "." << nano << " "
      << supported_currencies[src_index]
      << " to " << supported_currencies[dst_index] << std::endl;

    Money response;
    ClientContext context;
    Status status = stub_->Convert(&context, request, &response);

    if (status.ok()) {
      std::cout << unit << "." << nano << " "
        << supported_currencies[src_index]
        << " converted to "
        << response.units() << "."
        << response.nanos() << " "
        << response.currency_code() << std::endl;
    } else {
      std::cout << "Currency Conversion failed \n";
    }
  }

  bool CheckHealthStatus()
  {
    HealthCheckRequest request;
    request.set_service("CurrencyService");
    HealthCheckResponse response;
    ClientContext context;
    Status s = hc_stub_->Check(&context, request, &response);
    if (s.ok()) {
      if (response.status() == grpc::health::v1::HealthCheckResponse::SERVING) {
        std::cout << "CurrencyService is up and running" << std::endl;
        return true;
      }
    }
    std::cout << "CurrencyService unreachable" << std::endl;
    return false;
  }

private:
  std::unique_ptr<CurrencyService::Stub> stub_;
  std::unique_ptr<Health::Stub> hc_stub_;
  std::vector<std::string> supported_currencies;
};

void RunClient(uint16_t port)
{
  CurrencyClient client(
      grpc::CreateChannel
      ("0.0.0.0:" + std::to_string(port), grpc::InsecureChannelCredentials()));

  if (client.CheckHealthStatus()) {
    client.GetSupportedCurrencies();
    while (true) {
      client.Convert();
      std::this_thread::sleep_for(std::chrono::milliseconds(2000));
    }
  }
}
}

int main(int argc, char **argv) {
  constexpr uint16_t default_port = 8800;
  uint16_t port;
  if (argc > 1)
  {
    port = atoi(argv[1]);
  }
  else
  {
    port = default_port;
  }

  RunClient(port);
  return 0;
}
