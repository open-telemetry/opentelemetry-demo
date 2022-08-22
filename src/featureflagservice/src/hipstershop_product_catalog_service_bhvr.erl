%%%-------------------------------------------------------------------
%% @doc Behaviour to implement for grpc service hipstershop.ProductCatalogService.
%% @end
%%%-------------------------------------------------------------------

%% this module was generated and should not be modified manually

-module(hipstershop_product_catalog_service_bhvr).

%% Unary RPC
-callback list_products(ctx:t(), ffs_demo_pb:empty()) ->
    {ok, ffs_demo_pb:list_products_response(), ctx:t()} | grpcbox_stream:grpc_error_response().

%% Unary RPC
-callback get_product(ctx:t(), ffs_demo_pb:get_product_request()) ->
    {ok, ffs_demo_pb:product(), ctx:t()} | grpcbox_stream:grpc_error_response().

%% Unary RPC
-callback search_products(ctx:t(), ffs_demo_pb:search_products_request()) ->
    {ok, ffs_demo_pb:search_products_response(), ctx:t()} | grpcbox_stream:grpc_error_response().

