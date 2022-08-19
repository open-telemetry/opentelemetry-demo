%%%-------------------------------------------------------------------
%% @doc Behaviour to implement for grpc service hipstershop.CartService.
%% @end
%%%-------------------------------------------------------------------

%% this module was generated and should not be modified manually

-module(hipstershop_cart_service_bhvr).

%% Unary RPC
-callback add_item(ctx:t(), ffs_demo_pb:add_item_request()) ->
    {ok, ffs_demo_pb:empty(), ctx:t()} | grpcbox_stream:grpc_error_response().

%% Unary RPC
-callback get_cart(ctx:t(), ffs_demo_pb:get_cart_request()) ->
    {ok, ffs_demo_pb:cart(), ctx:t()} | grpcbox_stream:grpc_error_response().

%% Unary RPC
-callback empty_cart(ctx:t(), ffs_demo_pb:empty_cart_request()) ->
    {ok, ffs_demo_pb:empty(), ctx:t()} | grpcbox_stream:grpc_error_response().

