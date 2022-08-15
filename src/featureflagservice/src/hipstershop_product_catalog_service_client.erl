%%%-------------------------------------------------------------------
%% @doc Client module for grpc service hipstershop.ProductCatalogService.
%% @end
%%%-------------------------------------------------------------------

%% this module was generated and should not be modified manually

-module(hipstershop_product_catalog_service_client).

-compile(export_all).
-compile(nowarn_export_all).

-include_lib("grpcbox/include/grpcbox.hrl").

-define(is_ctx(Ctx), is_tuple(Ctx) andalso element(1, Ctx) =:= ctx).

-define(SERVICE, 'hipstershop.ProductCatalogService').
-define(PROTO_MODULE, 'ffs_demo_pb').
-define(MARSHAL_FUN(T), fun(I) -> ?PROTO_MODULE:encode_msg(I, T) end).
-define(UNMARSHAL_FUN(T), fun(I) -> ?PROTO_MODULE:decode_msg(I, T) end).
-define(DEF(Input, Output, MessageType), #grpcbox_def{service=?SERVICE,
                                                      message_type=MessageType,
                                                      marshal_fun=?MARSHAL_FUN(Input),
                                                      unmarshal_fun=?UNMARSHAL_FUN(Output)}).

%% @doc Unary RPC
-spec list_products(ffs_demo_pb:empty()) ->
    {ok, ffs_demo_pb:list_products_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
list_products(Input) ->
    list_products(ctx:new(), Input, #{}).

-spec list_products(ctx:t() | ffs_demo_pb:empty(), ffs_demo_pb:empty() | grpcbox_client:options()) ->
    {ok, ffs_demo_pb:list_products_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
list_products(Ctx, Input) when ?is_ctx(Ctx) ->
    list_products(Ctx, Input, #{});
list_products(Input, Options) ->
    list_products(ctx:new(), Input, Options).

-spec list_products(ctx:t(), ffs_demo_pb:empty(), grpcbox_client:options()) ->
    {ok, ffs_demo_pb:list_products_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
list_products(Ctx, Input, Options) ->
    grpcbox_client:unary(Ctx, <<"/hipstershop.ProductCatalogService/ListProducts">>, Input, ?DEF(empty, list_products_response, <<"hipstershop.Empty">>), Options).

%% @doc Unary RPC
-spec get_product(ffs_demo_pb:get_product_request()) ->
    {ok, ffs_demo_pb:product(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
get_product(Input) ->
    get_product(ctx:new(), Input, #{}).

-spec get_product(ctx:t() | ffs_demo_pb:get_product_request(), ffs_demo_pb:get_product_request() | grpcbox_client:options()) ->
    {ok, ffs_demo_pb:product(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
get_product(Ctx, Input) when ?is_ctx(Ctx) ->
    get_product(Ctx, Input, #{});
get_product(Input, Options) ->
    get_product(ctx:new(), Input, Options).

-spec get_product(ctx:t(), ffs_demo_pb:get_product_request(), grpcbox_client:options()) ->
    {ok, ffs_demo_pb:product(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
get_product(Ctx, Input, Options) ->
    grpcbox_client:unary(Ctx, <<"/hipstershop.ProductCatalogService/GetProduct">>, Input, ?DEF(get_product_request, product, <<"hipstershop.GetProductRequest">>), Options).

%% @doc Unary RPC
-spec search_products(ffs_demo_pb:search_products_request()) ->
    {ok, ffs_demo_pb:search_products_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
search_products(Input) ->
    search_products(ctx:new(), Input, #{}).

-spec search_products(ctx:t() | ffs_demo_pb:search_products_request(), ffs_demo_pb:search_products_request() | grpcbox_client:options()) ->
    {ok, ffs_demo_pb:search_products_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
search_products(Ctx, Input) when ?is_ctx(Ctx) ->
    search_products(Ctx, Input, #{});
search_products(Input, Options) ->
    search_products(ctx:new(), Input, Options).

-spec search_products(ctx:t(), ffs_demo_pb:search_products_request(), grpcbox_client:options()) ->
    {ok, ffs_demo_pb:search_products_response(), grpcbox:metadata()} | grpcbox_stream:grpc_error_response() | {error, any()}.
search_products(Ctx, Input, Options) ->
    grpcbox_client:unary(Ctx, <<"/hipstershop.ProductCatalogService/SearchProducts">>, Input, ?DEF(search_products_request, search_products_response, <<"hipstershop.SearchProductsRequest">>), Options).

