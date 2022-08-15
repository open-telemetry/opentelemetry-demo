%%%-------------------------------------------------------------------
%% @doc Client module for grpc service hipstershop.EmailService.
%% @end
%%%-------------------------------------------------------------------

%% this module was generated and should not be modified manually

-module(hipstershop_email_service_client).

-compile(export_all).
-compile(nowarn_export_all).

-include_lib("grpcbox/include/grpcbox.hrl").

-define(is_ctx(Ctx), is_tuple(Ctx) andalso element(1, Ctx) =:= ctx).

-define(SERVICE, 'hipstershop.EmailService').
-define(PROTO_MODULE, 'ffs_demo_pb').
-define(MARSHAL_FUN(T), fun(I) -> ?PROTO_MODULE:encode_msg(I, T) end).
-define(UNMARSHAL_FUN(T), fun(I) -> ?PROTO_MODULE:decode_msg(I, T) end).
-define(DEF(Input, Output, MessageType), #grpcbox_def{service=?SERVICE,
                                                      message_type=MessageType,
                                                      marshal_fun=?MARSHAL_FUN(Input),
                                                      unmarshal_fun=?UNMARSHAL_FUN(Output)}).

%% @doc Unary RPC
-spec send_order_confirmation(ffs_demo_pb:send_order_confirmation_request()) ->
    {ok, ffs_demo_pb:empty(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
send_order_confirmation(Input) ->
    send_order_confirmation(ctx:new(), Input, #{}).

-spec send_order_confirmation(ctx:t() | ffs_demo_pb:send_order_confirmation_request(), ffs_demo_pb:send_order_confirmation_request() | grpcbox_client:options()) ->
    {ok, ffs_demo_pb:empty(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
send_order_confirmation(Ctx, Input) when ?is_ctx(Ctx) ->
    send_order_confirmation(Ctx, Input, #{});
send_order_confirmation(Input, Options) ->
    send_order_confirmation(ctx:new(), Input, Options).

-spec send_order_confirmation(ctx:t(), ffs_demo_pb:send_order_confirmation_request(), grpcbox_client:options()) ->
    {ok, ffs_demo_pb:empty(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
send_order_confirmation(Ctx, Input, Options) ->
    grpcbox_client:unary(Ctx, <<"/hipstershop.EmailService/SendOrderConfirmation">>, Input, ?DEF(send_order_confirmation_request, empty, <<"hipstershop.SendOrderConfirmationRequest">>), Options).

