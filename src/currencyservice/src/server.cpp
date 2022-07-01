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

namespace
{
class CurrencyServer final : public CurrencyService::Service
{
    Status GetSupportedCurrencies(ServerContext* context,
    	const Empty* request,
    	GetSupportedCurrenciesResponse* response) override
    {
    	response->add_currency_codes("EUR");
    	response->add_currency_codes("USD");
    	return Status::OK;
    }
    Status Convert(ServerContext* context,
    	const CurrencyConversionRequest* request,
    	Money* response) override
    {

    	return Status::OK;
    }
};

void RunServer(uint16_t port)
{
  std::string address("0.0.0.0:" + std::to_string(port));
  CurrencyServer service;
  ServerBuilder builder;

  builder.RegisterService(&service);
  builder.AddListeningPort(address, grpc::InsecureServerCredentials());

  std::unique_ptr<Server> server(builder.BuildAndStart());
  std::cout << "Server listening on port: " << address << std::endl;
  server->Wait();
  server->Shutdown();
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

  RunServer(port);
  return 0;
}
