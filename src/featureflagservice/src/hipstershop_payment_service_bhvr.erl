%%%-------------------------------------------------------------------
%% @doc Behaviour to implement for grpc service hipstershop.PaymentService.
%% @end
%%%-------------------------------------------------------------------

%% this module was generated and should not be modified manually

-module(hipstershop_payment_service_bhvr).

%% Unary RPC
-callback charge(ctx:t(), ffs_demo_pb:charge_request()) ->
    {ok, ffs_demo_pb:charge_response(), ctx:t()} | grpcbox_stream:grpc_error_response().

