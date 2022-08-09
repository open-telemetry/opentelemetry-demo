%%%-------------------------------------------------------------------
%% @doc Behaviour to implement for grpc service hipstershop.EmailService.
%% @end
%%%-------------------------------------------------------------------

%% this module was generated and should not be modified manually

-module(hipstershop_email_service_bhvr).

%% Unary RPC
-callback send_order_confirmation(ctx:t(), ffs_demo_pb:send_order_confirmation_request()) ->
    {ok, ffs_demo_pb:empty(), ctx:t()} | grpcbox_stream:grpc_error_response().

