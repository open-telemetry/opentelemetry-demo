%%%-------------------------------------------------------------------
%% @doc Behaviour to implement for grpc service FeatureFlagService.
%% @end
%%%-------------------------------------------------------------------

%% this module was generated and should not be modified manually

-module(ffs_service_bhvr).

%% Unary RPC
-callback get_flag(ctx:t(), ffs_featureflag_pb:get_flag_request()) ->
    {ok, ffs_featureflag_pb:get_flag_response(), ctx:t()} | grpcbox_stream:grpc_error_response().

%% Unary RPC
-callback create_flag(ctx:t(), ffs_featureflag_pb:create_flag_request()) ->
    {ok, ffs_featureflag_pb:create_flag_response(), ctx:t()} | grpcbox_stream:grpc_error_response().

%% Unary RPC
-callback update_flag(ctx:t(), ffs_featureflag_pb:update_flag_request()) ->
    {ok, ffs_featureflag_pb:update_flag_response(), ctx:t()} | grpcbox_stream:grpc_error_response().

%% Unary RPC
-callback list_flags(ctx:t(), ffs_featureflag_pb:list_flags_request()) ->
    {ok, ffs_featureflag_pb:list_flags_response(), ctx:t()} | grpcbox_stream:grpc_error_response().

%% Unary RPC
-callback delete_flag(ctx:t(), ffs_featureflag_pb:delete_flag_request()) ->
    {ok, ffs_featureflag_pb:delete_flag_response(), ctx:t()} | grpcbox_stream:grpc_error_response().

