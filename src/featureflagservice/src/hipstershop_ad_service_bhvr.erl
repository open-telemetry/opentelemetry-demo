%%%-------------------------------------------------------------------
%% @doc Behaviour to implement for grpc service hipstershop.AdService.
%% @end
%%%-------------------------------------------------------------------

%% this module was generated and should not be modified manually

-module(hipstershop_ad_service_bhvr).

%% Unary RPC
-callback get_ads(ctx:t(), ffs_demo_pb:ad_request()) ->
    {ok, ffs_demo_pb:ad_response(), ctx:t()} | grpcbox_stream:grpc_error_response().

