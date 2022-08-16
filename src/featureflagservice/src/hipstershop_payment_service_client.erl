%%%-------------------------------------------------------------------
%% @doc Client module for grpc service hipstershop.PaymentService.
%% @end
%%%-------------------------------------------------------------------

%% this module was generated and should not be modified manually

-module(hipstershop_payment_service_client).

-compile(export_all).
-compile(nowarn_export_all).

-include_lib("grpcbox/include/grpcbox.hrl").

-define(is_ctx(Ctx), is_tuple(Ctx) andalso element(1, Ctx) =:= ctx).

-define(SERVICE, 'hipstershop.PaymentService').
-define(PROTO_MODULE, 'ffs_demo_pb').
-define(MARSHAL_FUN(T), fun(I) -> ?PROTO_MODULE:encode_msg(I, T) end).
-define(UNMARSHAL_FUN(T), fun(I) -> ?PROTO_MODULE:decode_msg(I, T) end).
-define(DEF(Input, Output, MessageType), #grpcbox_def{service=?SERVICE,
                                                      message_type=MessageType,
                                                      marshal_fun=?MARSHAL_FUN(Input),
                                                      unmarshal_fun=?UNMARSHAL_FUN(Output)}).

%% @doc Unary RPC
-spec charge(ffs_demo_pb:charge_request()) ->
    {ok, ffs_demo_pb:charge_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
charge(Input) ->
    charge(ctx:new(), Input, #{}).

-spec charge(ctx:t() | ffs_demo_pb:charge_request(), ffs_demo_pb:charge_request() | grpcbox_client:options()) ->
    {ok, ffs_demo_pb:charge_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
charge(Ctx, Input) when ?is_ctx(Ctx) ->
    charge(Ctx, Input, #{});
charge(Input, Options) ->
    charge(ctx:new(), Input, Options).

-spec charge(ctx:t(), ffs_demo_pb:charge_request(), grpcbox_client:options()) ->
    {ok, ffs_demo_pb:charge_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
charge(Ctx, Input, Options) ->
    grpcbox_client:unary(Ctx, <<"/hipstershop.PaymentService/Charge">>, Input, ?DEF(charge_request, charge_response, <<"hipstershop.ChargeRequest">>), Options).

