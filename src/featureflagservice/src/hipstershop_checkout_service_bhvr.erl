%%%-------------------------------------------------------------------
%% @doc Behaviour to implement for grpc service hipstershop.CheckoutService.
%% @end
%%%-------------------------------------------------------------------

%% this module was generated and should not be modified manually

-module(hipstershop_checkout_service_bhvr).

%% Unary RPC
-callback place_order(ctx:t(), ffs_demo_pb:place_order_request()) ->
    {ok, ffs_demo_pb:place_order_response(), ctx:t()} | grpcbox_stream:grpc_error_response().

