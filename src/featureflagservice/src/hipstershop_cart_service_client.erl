%%%-------------------------------------------------------------------
%% @doc Client module for grpc service hipstershop.CartService.
%% @end
%%%-------------------------------------------------------------------

%% this module was generated and should not be modified manually

-module(hipstershop_cart_service_client).

-compile(export_all).
-compile(nowarn_export_all).

-include_lib("grpcbox/include/grpcbox.hrl").

-define(is_ctx(Ctx), is_tuple(Ctx) andalso element(1, Ctx) =:= ctx).

-define(SERVICE, 'hipstershop.CartService').
-define(PROTO_MODULE, 'ffs_demo_pb').
-define(MARSHAL_FUN(T), fun(I) -> ?PROTO_MODULE:encode_msg(I, T) end).
-define(UNMARSHAL_FUN(T), fun(I) -> ?PROTO_MODULE:decode_msg(I, T) end).
-define(DEF(Input, Output, MessageType), #grpcbox_def{service=?SERVICE,
                                                      message_type=MessageType,
                                                      marshal_fun=?MARSHAL_FUN(Input),
                                                      unmarshal_fun=?UNMARSHAL_FUN(Output)}).

%% @doc Unary RPC
-spec add_item(ffs_demo_pb:add_item_request()) ->
    {ok, ffs_demo_pb:empty(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
add_item(Input) ->
    add_item(ctx:new(), Input, #{}).

-spec add_item(ctx:t() | ffs_demo_pb:add_item_request(), ffs_demo_pb:add_item_request() | grpcbox_client:options()) ->
    {ok, ffs_demo_pb:empty(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
add_item(Ctx, Input) when ?is_ctx(Ctx) ->
    add_item(Ctx, Input, #{});
add_item(Input, Options) ->
    add_item(ctx:new(), Input, Options).

-spec add_item(ctx:t(), ffs_demo_pb:add_item_request(), grpcbox_client:options()) ->
    {ok, ffs_demo_pb:empty(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
add_item(Ctx, Input, Options) ->
    grpcbox_client:unary(Ctx, <<"/hipstershop.CartService/AddItem">>, Input, ?DEF(add_item_request, empty, <<"hipstershop.AddItemRequest">>), Options).

%% @doc Unary RPC
-spec get_cart(ffs_demo_pb:get_cart_request()) ->
    {ok, ffs_demo_pb:cart(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
get_cart(Input) ->
    get_cart(ctx:new(), Input, #{}).

-spec get_cart(ctx:t() | ffs_demo_pb:get_cart_request(), ffs_demo_pb:get_cart_request() | grpcbox_client:options()) ->
    {ok, ffs_demo_pb:cart(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
get_cart(Ctx, Input) when ?is_ctx(Ctx) ->
    get_cart(Ctx, Input, #{});
get_cart(Input, Options) ->
    get_cart(ctx:new(), Input, Options).

-spec get_cart(ctx:t(), ffs_demo_pb:get_cart_request(), grpcbox_client:options()) ->
    {ok, ffs_demo_pb:cart(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
get_cart(Ctx, Input, Options) ->
    grpcbox_client:unary(Ctx, <<"/hipstershop.CartService/GetCart">>, Input, ?DEF(get_cart_request, cart, <<"hipstershop.GetCartRequest">>), Options).

%% @doc Unary RPC
-spec empty_cart(ffs_demo_pb:empty_cart_request()) ->
    {ok, ffs_demo_pb:empty(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
empty_cart(Input) ->
    empty_cart(ctx:new(), Input, #{}).

-spec empty_cart(ctx:t() | ffs_demo_pb:empty_cart_request(), ffs_demo_pb:empty_cart_request() | grpcbox_client:options()) ->
    {ok, ffs_demo_pb:empty(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
empty_cart(Ctx, Input) when ?is_ctx(Ctx) ->
    empty_cart(Ctx, Input, #{});
empty_cart(Input, Options) ->
    empty_cart(ctx:new(), Input, Options).

-spec empty_cart(ctx:t(), ffs_demo_pb:empty_cart_request(), grpcbox_client:options()) ->
    {ok, ffs_demo_pb:empty(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
empty_cart(Ctx, Input, Options) ->
    grpcbox_client:unary(Ctx, <<"/hipstershop.CartService/EmptyCart">>, Input, ?DEF(empty_cart_request, empty, <<"hipstershop.EmptyCartRequest">>), Options).

