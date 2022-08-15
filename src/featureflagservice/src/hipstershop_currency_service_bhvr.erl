%%%-------------------------------------------------------------------
%% @doc Behaviour to implement for grpc service hipstershop.CurrencyService.
%% @end
%%%-------------------------------------------------------------------

%% this module was generated and should not be modified manually

-module(hipstershop_currency_service_bhvr).

%% Unary RPC
-callback get_supported_currencies(ctx:t(), ffs_demo_pb:empty()) ->
    {ok, ffs_demo_pb:get_supported_currencies_response(), ctx:t()} | grpcbox_stream:grpc_error_response().

%% Unary RPC
-callback convert(ctx:t(), ffs_demo_pb:currency_conversion_request()) ->
    {ok, ffs_demo_pb:money(), ctx:t()} | grpcbox_stream:grpc_error_response().

