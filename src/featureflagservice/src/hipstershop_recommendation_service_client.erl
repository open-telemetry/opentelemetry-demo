%%%-------------------------------------------------------------------
%% @doc Client module for grpc service hipstershop.RecommendationService.
%% @end
%%%-------------------------------------------------------------------

%% this module was generated and should not be modified manually

-module(hipstershop_recommendation_service_client).

-compile(export_all).
-compile(nowarn_export_all).

-include_lib("grpcbox/include/grpcbox.hrl").

-define(is_ctx(Ctx), is_tuple(Ctx) andalso element(1, Ctx) =:= ctx).

-define(SERVICE, 'hipstershop.RecommendationService').
-define(PROTO_MODULE, 'ffs_demo_pb').
-define(MARSHAL_FUN(T), fun(I) -> ?PROTO_MODULE:encode_msg(I, T) end).
-define(UNMARSHAL_FUN(T), fun(I) -> ?PROTO_MODULE:decode_msg(I, T) end).
-define(DEF(Input, Output, MessageType), #grpcbox_def{service=?SERVICE,
                                                      message_type=MessageType,
                                                      marshal_fun=?MARSHAL_FUN(Input),
                                                      unmarshal_fun=?UNMARSHAL_FUN(Output)}).

%% @doc Unary RPC
-spec list_recommendations(ffs_demo_pb:list_recommendations_request()) ->
    {ok, ffs_demo_pb:list_recommendations_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
list_recommendations(Input) ->
    list_recommendations(ctx:new(), Input, #{}).

-spec list_recommendations(ctx:t() | ffs_demo_pb:list_recommendations_request(), ffs_demo_pb:list_recommendations_request() | grpcbox_client:options()) ->
    {ok, ffs_demo_pb:list_recommendations_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
list_recommendations(Ctx, Input) when ?is_ctx(Ctx) ->
    list_recommendations(Ctx, Input, #{});
list_recommendations(Input, Options) ->
    list_recommendations(ctx:new(), Input, Options).

-spec list_recommendations(ctx:t(), ffs_demo_pb:list_recommendations_request(), grpcbox_client:options()) ->
    {ok, ffs_demo_pb:list_recommendations_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
list_recommendations(Ctx, Input, Options) ->
    grpcbox_client:unary(Ctx, <<"/hipstershop.RecommendationService/ListRecommendations">>, Input, ?DEF(list_recommendations_request, list_recommendations_response, <<"hipstershop.ListRecommendationsRequest">>), Options).

