%%%-------------------------------------------------------------------
%% @doc Behaviour to implement for grpc service hipstershop.RecommendationService.
%% @end
%%%-------------------------------------------------------------------

%% this module was generated and should not be modified manually

-module(hipstershop_recommendation_service_bhvr).

%% Unary RPC
-callback list_recommendations(ctx:t(), ffs_demo_pb:list_recommendations_request()) ->
    {ok, ffs_demo_pb:list_recommendations_response(), ctx:t()} | grpcbox_stream:grpc_error_response().

