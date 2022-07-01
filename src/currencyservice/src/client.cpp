#include <iostream>
#include <demo.grpc.pb.h>

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

namespace
{
class CurrencyClient
{
public:
  CurrencyClient(std::shared_ptr<Channel> channel)
  : stub_(CurrencyService::NewStub(channel, StubOptions{})) {}

  void GetSupportedCurrencies()
  {
    Empty request;
    GetSupportedCurrenciesResponse response;
    ClientContext context;

    Status status = stub_->GetSupportedCurrencies(&context, request, &response);

    for (int i = 0; i < response.currency_codes_size(); i++) {
      std::cout << response.currency_codes(i) << std::endl;
    }

  }
private:
  std::unique_ptr<CurrencyService::Stub> stub_;
};

void RunClient(uint16_t port)
{
  CurrencyClient client(
      grpc::CreateChannel
      ("0.0.0.0:" + std::to_string(port), grpc::InsecureChannelCredentials()));
  client.GetSupportedCurrencies();
}
}



int main(int argc, char **argv) {

  std::cout << "Helloworld" << std::endl;
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
