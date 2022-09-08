%%%-------------------------------------------------------------------
%% @doc Behaviour to implement for grpc service hipstershop.ShippingService.
%% @end
%%%-------------------------------------------------------------------

%% this module was generated and should not be modified manually

-module(hipstershop_shipping_service_bhvr).

%% Unary RPC
-callback get_quote(ctx:t(), ffs_demo_pb:get_quote_request()) ->
    {ok, ffs_demo_pb:get_quote_response(), ctx:t()} | grpcbox_stream:grpc_error_response().

%% Unary RPC
-callback ship_order(ctx:t(), ffs_demo_pb:ship_order_request()) ->
    {ok, ffs_demo_pb:ship_order_response(), ctx:t()} | grpcbox_stream:grpc_error_response().

