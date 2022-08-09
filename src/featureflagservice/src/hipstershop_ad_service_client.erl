%%%-------------------------------------------------------------------
%% @doc Client module for grpc service hipstershop.AdService.
%% @end
%%%-------------------------------------------------------------------

%% this module was generated and should not be modified manually

-module(hipstershop_ad_service_client).

-compile(export_all).
-compile(nowarn_export_all).

-include_lib("grpcbox/include/grpcbox.hrl").

-define(is_ctx(Ctx), is_tuple(Ctx) andalso element(1, Ctx) =:= ctx).

-define(SERVICE, 'hipstershop.AdService').
-define(PROTO_MODULE, 'ffs_demo_pb').
-define(MARSHAL_FUN(T), fun(I) -> ?PROTO_MODULE:encode_msg(I, T) end).
-define(UNMARSHAL_FUN(T), fun(I) -> ?PROTO_MODULE:decode_msg(I, T) end).
-define(DEF(Input, Output, MessageType), #grpcbox_def{service=?SERVICE,
                                                      message_type=MessageType,
                                                      marshal_fun=?MARSHAL_FUN(Input),
                                                      unmarshal_fun=?UNMARSHAL_FUN(Output)}).

%% @doc Unary RPC
-spec get_ads(ffs_demo_pb:ad_request()) ->
    {ok, ffs_demo_pb:ad_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
get_ads(Input) ->
    get_ads(ctx:new(), Input, #{}).

-spec get_ads(ctx:t() | ffs_demo_pb:ad_request(), ffs_demo_pb:ad_request() | grpcbox_client:options()) ->
    {ok, ffs_demo_pb:ad_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
get_ads(Ctx, Input) when ?is_ctx(Ctx) ->
    get_ads(Ctx, Input, #{});
get_ads(Input, Options) ->
    get_ads(ctx:new(), Input, Options).

-spec get_ads(ctx:t(), ffs_demo_pb:ad_request(), grpcbox_client:options()) ->
    {ok, ffs_demo_pb:ad_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
get_ads(Ctx, Input, Options) ->
    grpcbox_client:unary(Ctx, <<"/hipstershop.AdService/GetAds">>, Input, ?DEF(ad_request, ad_response, <<"hipstershop.AdRequest">>), Options).

