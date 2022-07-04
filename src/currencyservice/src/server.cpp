#include <iostream>
#include <math.h>
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



class CurrencyServer final : public CurrencyService::Service
{
    Status GetSupportedCurrencies(ServerContext* context,
    	const Empty* request,
    	GetSupportedCurrenciesResponse* response) override
    {
      for (auto &code : currency_conversion) {
        response->add_currency_codes(code.first);
      }
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
      Money from = request->from();
      string from_code = from.currency_code();
      double rate = currency_conversion[from_code];
      double one_euro = getDouble(from) / rate ;

      string to_code = request->to_code();
      double to_rate = currency_conversion[to_code];

      double final = one_euro * to_rate;
      getUnitsAndNanos(*response, final);
      response->set_currency_code(to_code);


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
