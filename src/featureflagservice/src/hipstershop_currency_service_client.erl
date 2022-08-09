%%%-------------------------------------------------------------------
%% @doc Client module for grpc service hipstershop.CurrencyService.
%% @end
%%%-------------------------------------------------------------------

%% this module was generated and should not be modified manually

-module(hipstershop_currency_service_client).

-compile(export_all).
-compile(nowarn_export_all).

-include_lib("grpcbox/include/grpcbox.hrl").

-define(is_ctx(Ctx), is_tuple(Ctx) andalso element(1, Ctx) =:= ctx).

-define(SERVICE, 'hipstershop.CurrencyService').
-define(PROTO_MODULE, 'ffs_demo_pb').
-define(MARSHAL_FUN(T), fun(I) -> ?PROTO_MODULE:encode_msg(I, T) end).
-define(UNMARSHAL_FUN(T), fun(I) -> ?PROTO_MODULE:decode_msg(I, T) end).
-define(DEF(Input, Output, MessageType), #grpcbox_def{service=?SERVICE,
                                                      message_type=MessageType,
                                                      marshal_fun=?MARSHAL_FUN(Input),
                                                      unmarshal_fun=?UNMARSHAL_FUN(Output)}).

%% @doc Unary RPC
-spec get_supported_currencies(ffs_demo_pb:empty()) ->
    {ok, ffs_demo_pb:get_supported_currencies_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
get_supported_currencies(Input) ->
    get_supported_currencies(ctx:new(), Input, #{}).

-spec get_supported_currencies(ctx:t() | ffs_demo_pb:empty(), ffs_demo_pb:empty() | grpcbox_client:options()) ->
    {ok, ffs_demo_pb:get_supported_currencies_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
get_supported_currencies(Ctx, Input) when ?is_ctx(Ctx) ->
    get_supported_currencies(Ctx, Input, #{});
get_supported_currencies(Input, Options) ->
    get_supported_currencies(ctx:new(), Input, Options).

-spec get_supported_currencies(ctx:t(), ffs_demo_pb:empty(), grpcbox_client:options()) ->
    {ok, ffs_demo_pb:get_supported_currencies_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
get_supported_currencies(Ctx, Input, Options) ->
    grpcbox_client:unary(Ctx, <<"/hipstershop.CurrencyService/GetSupportedCurrencies">>, Input, ?DEF(empty, get_supported_currencies_response, <<"hipstershop.Empty">>), Options).

%% @doc Unary RPC
-spec convert(ffs_demo_pb:currency_conversion_request()) ->
    {ok, ffs_demo_pb:money(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
convert(Input) ->
    convert(ctx:new(), Input, #{}).

-spec convert(ctx:t() | ffs_demo_pb:currency_conversion_request(), ffs_demo_pb:currency_conversion_request() | grpcbox_client:options()) ->
    {ok, ffs_demo_pb:money(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
convert(Ctx, Input) when ?is_ctx(Ctx) ->
    convert(Ctx, Input, #{});
convert(Input, Options) ->
    convert(ctx:new(), Input, Options).

-spec convert(ctx:t(), ffs_demo_pb:currency_conversion_request(), grpcbox_client:options()) ->
    {ok, ffs_demo_pb:money(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
convert(Ctx, Input, Options) ->
    grpcbox_client:unary(Ctx, <<"/hipstershop.CurrencyService/Convert">>, Input, ?DEF(currency_conversion_request, money, <<"hipstershop.CurrencyConversionRequest">>), Options).

