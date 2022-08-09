%%%-------------------------------------------------------------------
%% @doc Client module for grpc service hipstershop.FeatureFlagService.
%% @end
%%%-------------------------------------------------------------------

%% this module was generated and should not be modified manually

-module(ffs_service_client).

-compile(export_all).
-compile(nowarn_export_all).

-include_lib("grpcbox/include/grpcbox.hrl").

-define(is_ctx(Ctx), is_tuple(Ctx) andalso element(1, Ctx) =:= ctx).

-define(SERVICE, 'hipstershop.FeatureFlagService').
-define(PROTO_MODULE, 'ffs_demo_pb').
-define(MARSHAL_FUN(T), fun(I) -> ?PROTO_MODULE:encode_msg(I, T) end).
-define(UNMARSHAL_FUN(T), fun(I) -> ?PROTO_MODULE:decode_msg(I, T) end).
-define(DEF(Input, Output, MessageType), #grpcbox_def{service=?SERVICE,
                                                      message_type=MessageType,
                                                      marshal_fun=?MARSHAL_FUN(Input),
                                                      unmarshal_fun=?UNMARSHAL_FUN(Output)}).

%% @doc Unary RPC
-spec get_flag(ffs_demo_pb:get_flag_request()) ->
    {ok, ffs_demo_pb:get_flag_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
get_flag(Input) ->
    get_flag(ctx:new(), Input, #{}).

-spec get_flag(ctx:t() | ffs_demo_pb:get_flag_request(), ffs_demo_pb:get_flag_request() | grpcbox_client:options()) ->
    {ok, ffs_demo_pb:get_flag_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
get_flag(Ctx, Input) when ?is_ctx(Ctx) ->
    get_flag(Ctx, Input, #{});
get_flag(Input, Options) ->
    get_flag(ctx:new(), Input, Options).

-spec get_flag(ctx:t(), ffs_demo_pb:get_flag_request(), grpcbox_client:options()) ->
    {ok, ffs_demo_pb:get_flag_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
get_flag(Ctx, Input, Options) ->
    grpcbox_client:unary(Ctx, <<"/hipstershop.FeatureFlagService/GetFlag">>, Input, ?DEF(get_flag_request, get_flag_response, <<"hipstershop.GetFlagRequest">>), Options).

%% @doc Unary RPC
-spec create_flag(ffs_demo_pb:create_flag_request()) ->
    {ok, ffs_demo_pb:create_flag_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
create_flag(Input) ->
    create_flag(ctx:new(), Input, #{}).

-spec create_flag(ctx:t() | ffs_demo_pb:create_flag_request(), ffs_demo_pb:create_flag_request() | grpcbox_client:options()) ->
    {ok, ffs_demo_pb:create_flag_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
create_flag(Ctx, Input) when ?is_ctx(Ctx) ->
    create_flag(Ctx, Input, #{});
create_flag(Input, Options) ->
    create_flag(ctx:new(), Input, Options).

-spec create_flag(ctx:t(), ffs_demo_pb:create_flag_request(), grpcbox_client:options()) ->
    {ok, ffs_demo_pb:create_flag_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
create_flag(Ctx, Input, Options) ->
    grpcbox_client:unary(Ctx, <<"/hipstershop.FeatureFlagService/CreateFlag">>, Input, ?DEF(create_flag_request, create_flag_response, <<"hipstershop.CreateFlagRequest">>), Options).

%% @doc Unary RPC
-spec update_flag(ffs_demo_pb:update_flag_request()) ->
    {ok, ffs_demo_pb:update_flag_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
update_flag(Input) ->
    update_flag(ctx:new(), Input, #{}).

-spec update_flag(ctx:t() | ffs_demo_pb:update_flag_request(), ffs_demo_pb:update_flag_request() | grpcbox_client:options()) ->
    {ok, ffs_demo_pb:update_flag_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
update_flag(Ctx, Input) when ?is_ctx(Ctx) ->
    update_flag(Ctx, Input, #{});
update_flag(Input, Options) ->
    update_flag(ctx:new(), Input, Options).

-spec update_flag(ctx:t(), ffs_demo_pb:update_flag_request(), grpcbox_client:options()) ->
    {ok, ffs_demo_pb:update_flag_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
update_flag(Ctx, Input, Options) ->
    grpcbox_client:unary(Ctx, <<"/hipstershop.FeatureFlagService/UpdateFlag">>, Input, ?DEF(update_flag_request, update_flag_response, <<"hipstershop.UpdateFlagRequest">>), Options).

%% @doc Unary RPC
-spec list_flags(ffs_demo_pb:list_flags_request()) ->
    {ok, ffs_demo_pb:list_flags_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
list_flags(Input) ->
    list_flags(ctx:new(), Input, #{}).

-spec list_flags(ctx:t() | ffs_demo_pb:list_flags_request(), ffs_demo_pb:list_flags_request() | grpcbox_client:options()) ->
    {ok, ffs_demo_pb:list_flags_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
list_flags(Ctx, Input) when ?is_ctx(Ctx) ->
    list_flags(Ctx, Input, #{});
list_flags(Input, Options) ->
    list_flags(ctx:new(), Input, Options).

-spec list_flags(ctx:t(), ffs_demo_pb:list_flags_request(), grpcbox_client:options()) ->
    {ok, ffs_demo_pb:list_flags_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
list_flags(Ctx, Input, Options) ->
    grpcbox_client:unary(Ctx, <<"/hipstershop.FeatureFlagService/ListFlags">>, Input, ?DEF(list_flags_request, list_flags_response, <<"hipstershop.ListFlagsRequest">>), Options).

%% @doc Unary RPC
-spec delete_flag(ffs_demo_pb:delete_flag_request()) ->
    {ok, ffs_demo_pb:delete_flag_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
delete_flag(Input) ->
    delete_flag(ctx:new(), Input, #{}).

-spec delete_flag(ctx:t() | ffs_demo_pb:delete_flag_request(), ffs_demo_pb:delete_flag_request() | grpcbox_client:options()) ->
    {ok, ffs_demo_pb:delete_flag_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
delete_flag(Ctx, Input) when ?is_ctx(Ctx) ->
    delete_flag(Ctx, Input, #{});
delete_flag(Input, Options) ->
    delete_flag(ctx:new(), Input, Options).

-spec delete_flag(ctx:t(), ffs_demo_pb:delete_flag_request(), grpcbox_client:options()) ->
    {ok, ffs_demo_pb:delete_flag_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
delete_flag(Ctx, Input, Options) ->
    grpcbox_client:unary(Ctx, <<"/hipstershop.FeatureFlagService/DeleteFlag">>, Input, ?DEF(delete_flag_request, delete_flag_response, <<"hipstershop.DeleteFlagRequest">>), Options).

