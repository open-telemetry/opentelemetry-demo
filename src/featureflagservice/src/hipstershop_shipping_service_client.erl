%%%-------------------------------------------------------------------
%% @doc Client module for grpc service hipstershop.ShippingService.
%% @end
%%%-------------------------------------------------------------------

%% this module was generated and should not be modified manually

-module(hipstershop_shipping_service_client).

-compile(export_all).
-compile(nowarn_export_all).

-include_lib("grpcbox/include/grpcbox.hrl").

-define(is_ctx(Ctx), is_tuple(Ctx) andalso element(1, Ctx) =:= ctx).

-define(SERVICE, 'hipstershop.ShippingService').
-define(PROTO_MODULE, 'ffs_demo_pb').
-define(MARSHAL_FUN(T), fun(I) -> ?PROTO_MODULE:encode_msg(I, T) end).
-define(UNMARSHAL_FUN(T), fun(I) -> ?PROTO_MODULE:decode_msg(I, T) end).
-define(DEF(Input, Output, MessageType), #grpcbox_def{service=?SERVICE,
                                                      message_type=MessageType,
                                                      marshal_fun=?MARSHAL_FUN(Input),
                                                      unmarshal_fun=?UNMARSHAL_FUN(Output)}).

%% @doc Unary RPC
-spec get_quote(ffs_demo_pb:get_quote_request()) ->
    {ok, ffs_demo_pb:get_quote_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
get_quote(Input) ->
    get_quote(ctx:new(), Input, #{}).

-spec get_quote(ctx:t() | ffs_demo_pb:get_quote_request(), ffs_demo_pb:get_quote_request() | grpcbox_client:options()) ->
    {ok, ffs_demo_pb:get_quote_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
get_quote(Ctx, Input) when ?is_ctx(Ctx) ->
    get_quote(Ctx, Input, #{});
get_quote(Input, Options) ->
    get_quote(ctx:new(), Input, Options).

-spec get_quote(ctx:t(), ffs_demo_pb:get_quote_request(), grpcbox_client:options()) ->
    {ok, ffs_demo_pb:get_quote_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
get_quote(Ctx, Input, Options) ->
    grpcbox_client:unary(Ctx, <<"/hipstershop.ShippingService/GetQuote">>, Input, ?DEF(get_quote_request, get_quote_response, <<"hipstershop.GetQuoteRequest">>), Options).

%% @doc Unary RPC
-spec ship_order(ffs_demo_pb:ship_order_request()) ->
    {ok, ffs_demo_pb:ship_order_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
ship_order(Input) ->
    ship_order(ctx:new(), Input, #{}).

-spec ship_order(ctx:t() | ffs_demo_pb:ship_order_request(), ffs_demo_pb:ship_order_request() | grpcbox_client:options()) ->
    {ok, ffs_demo_pb:ship_order_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
ship_order(Ctx, Input) when ?is_ctx(Ctx) ->
    ship_order(Ctx, Input, #{});
ship_order(Input, Options) ->
    ship_order(ctx:new(), Input, Options).

-spec ship_order(ctx:t(), ffs_demo_pb:ship_order_request(), grpcbox_client:options()) ->
    {ok, ffs_demo_pb:ship_order_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
ship_order(Ctx, Input, Options) ->
    grpcbox_client:unary(Ctx, <<"/hipstershop.ShippingService/ShipOrder">>, Input, ?DEF(ship_order_request, ship_order_response, <<"hipstershop.ShipOrderRequest">>), Options).

