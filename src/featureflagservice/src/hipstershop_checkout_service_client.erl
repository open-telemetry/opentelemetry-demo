%%%-------------------------------------------------------------------
%% @doc Client module for grpc service hipstershop.CheckoutService.
%% @end
%%%-------------------------------------------------------------------

%% this module was generated and should not be modified manually

-module(hipstershop_checkout_service_client).

-compile(export_all).
-compile(nowarn_export_all).

-include_lib("grpcbox/include/grpcbox.hrl").

-define(is_ctx(Ctx), is_tuple(Ctx) andalso element(1, Ctx) =:= ctx).

-define(SERVICE, 'hipstershop.CheckoutService').
-define(PROTO_MODULE, 'ffs_demo_pb').
-define(MARSHAL_FUN(T), fun(I) -> ?PROTO_MODULE:encode_msg(I, T) end).
-define(UNMARSHAL_FUN(T), fun(I) -> ?PROTO_MODULE:decode_msg(I, T) end).
-define(DEF(Input, Output, MessageType), #grpcbox_def{service=?SERVICE,
                                                      message_type=MessageType,
                                                      marshal_fun=?MARSHAL_FUN(Input),
                                                      unmarshal_fun=?UNMARSHAL_FUN(Output)}).

%% @doc Unary RPC
-spec place_order(ffs_demo_pb:place_order_request()) ->
    {ok, ffs_demo_pb:place_order_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
place_order(Input) ->
    place_order(ctx:new(), Input, #{}).

-spec place_order(ctx:t() | ffs_demo_pb:place_order_request(), ffs_demo_pb:place_order_request() | grpcbox_client:options()) ->
    {ok, ffs_demo_pb:place_order_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
place_order(Ctx, Input) when ?is_ctx(Ctx) ->
    place_order(Ctx, Input, #{});
place_order(Input, Options) ->
    place_order(ctx:new(), Input, Options).

-spec place_order(ctx:t(), ffs_demo_pb:place_order_request(), grpcbox_client:options()) ->
    {ok, ffs_demo_pb:place_order_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
place_order(Ctx, Input, Options) ->
    grpcbox_client:unary(Ctx, <<"/hipstershop.CheckoutService/PlaceOrder">>, Input, ?DEF(place_order_request, place_order_response, <<"hipstershop.PlaceOrderRequest">>), Options).

