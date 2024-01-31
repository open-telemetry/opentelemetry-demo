% Copyright The OpenTelemetry Authors
%
% Licensed under the Apache License, Version 2.0 (the "License");
% you may not use this file except in compliance with the License.
% You may obtain a copy of the License at
%
%     http://www.apache.org/licenses/LICENSE-2.0
%
% Unless required by applicable law or agreed to in writing, software
% distributed under the License is distributed on an "AS IS" BASIS,
% WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
% See the License for the specific language governing permissions and
% limitations under the License.

-module(ffs_service).

-behaviour(ffs_service_bhvr).

-export([evaluate_probability_feature_flag/2,
  get_feature_flag_value/2,
  create_flag/2,
  update_flag_value/2,
  list_flags/2,
  delete_flag/2]).

-include_lib("grpcbox/include/grpcbox.hrl").

-include_lib("opentelemetry_api/include/otel_tracer.hrl").

-spec get_feature_flag_value(ctx:t(), ffs_demo_pb:get_feature_flag_value_request()) ->
  {ok, ffs_demo_pb:get_feature_flag_value_response(), ctx:t()} | grpcbox_stream:grpc_error_response().
get_feature_flag_value(Ctx, #{name := Name}) ->
  case 'Elixir.Featureflagservice.FeatureFlags':get_feature_flag_by_name(Name) of
    nil ->
      % Do not fail with a GRPC error when feature flag has not been configured, instead just return 0.
      % This allows services to seamlessly introduce new feature flags without requiring that every
      % deployment of the demo immediately sets them.
      {ok, #{value => 0.0}, Ctx};

    #{'__struct__' := 'Elixir.Featureflagservice.FeatureFlags.FeatureFlag',
      enabled := Value
    } ->

      ?set_attribute('app.featureflag.name', Name),
      ?set_attribute('app.featureflag.raw_value', Value),

      {ok, #{value => Value}, Ctx};

    _ ->
      {grpc_error, {?GRPC_STATUS_INTERNAL, <<"unexpected response from get_feature_flag_by_name">>}}

  end.

-spec evaluate_probability_feature_flag(ctx:t(), ffs_demo_pb:evaluate_probability_feature_flag_request()) ->
  {ok, ffs_demo_pb:evaluate_probability_feature_flag_response(), ctx:t()} | grpcbox_stream:grpc_error_response().
evaluate_probability_feature_flag(Ctx, #{name := Name}) ->
  case 'Elixir.Featureflagservice.FeatureFlags':get_feature_flag_by_name(Name) of
    nil ->
      % Do not fail with a GRPC error when feature flag has not been configured, instead just return false.
      % This allows services to seamlessly introduce new feature flags without requiring that every
      % deployment of the demo immediately sets them.
      {ok, #{enabled => false}, Ctx};

    #{'__struct__' := 'Elixir.Featureflagservice.FeatureFlags.FeatureFlag',
      enabled := RawValue
    } ->
      RandomNumber = rand:uniform(),
      FlagEnabledValue = RandomNumber =< RawValue,

      ?set_attribute('app.featureflag.name', Name),
      ?set_attribute('app.featureflag.raw_value', RawValue),
      ?set_attribute('app.featureflag.enabled', FlagEnabledValue),

      {ok, #{enabled => FlagEnabledValue}, Ctx};

    _ ->
      {grpc_error, {?GRPC_STATUS_INTERNAL, <<"unexpected response from get_feature_flag_by_name">>}}

  end.

-spec create_flag(ctx:t(), ffs_demo_pb:create_flag_request()) ->
  {ok, ffs_demo_pb:create_flag_response(), ctx:t()} | grpcbox_stream:grpc_error_response().
create_flag(Ctx, Flag) ->
  case Flag of
    nil ->
      {grpc_error, {?GRPC_STATUS_INVALID_ARGUMENT, <<"Flag is nil">>}};

    #{
      name := Name,
      description := Description,
      value := Value
    } ->
      'Elixir.Featureflagservice.FeatureFlags':create_feature_flag(#{
        name => Name,
        description => Description,
        enabled => Value
      }),

      ?set_attribute('app.featureflag.name', Name),
      ?set_attribute('app.featureflag.raw_value', Value),

      {ok, #{}, Ctx};

    _ ->
      {grpc_error, {?GRPC_STATUS_INVALID_ARGUMENT, <<"Malformed flag definition">>}}

  end.

-spec update_flag_value(ctx:t(), ffs_demo_pb:update_flag_value_request()) ->
  {ok, ffs_demo_pb:update_flag_value_response(), ctx:t()} | grpcbox_stream:grpc_error_response().
update_flag_value(Ctx, #{name := Name, value := Value}) ->
  Flag = 'Elixir.Featureflagservice.FeatureFlags':get_feature_flag_by_name(Name),
  case Flag of
    nil ->
      {grpc_error, {?GRPC_STATUS_NOT_FOUND, <<"the requested feature flag does not exist">>}};

    #{'__struct__' := 'Elixir.Featureflagservice.FeatureFlags.FeatureFlag'} ->
      'Elixir.Featureflagservice.FeatureFlags':update_feature_flag(
        Flag,
        #{enabled => Value}
      ),

      ?set_attribute('app.featureflag.name', Name),
      ?set_attribute('app.featureflag.raw_value', Value),

      {ok, #{}, Ctx};

    _ ->
      {grpc_error, {?GRPC_STATUS_INTERNAL, <<"unexpected response from get_feature_flag_by_name">>}}
  end.

-spec list_flags(ctx:t(), ffs_demo_pb:list_flags_request()) ->
  {ok, ffs_demo_pb:list_flags_response(), ctx:t()} | grpcbox_stream:grpc_error_response().
list_flags(Ctx, _) ->
  Flags = lists:map(fun unpack_flag/1, 'Elixir.Featureflagservice.FeatureFlags':list_feature_flags()),
  {ok, #{flag => Flags}, Ctx}.

unpack_flag(Flag) ->
  case Flag of
    #{'__struct__' := 'Elixir.Featureflagservice.FeatureFlags.FeatureFlag',
      name := Name,
      description := Description,
      enabled := Value
    } ->
      #{name => Name,
        description => Description,
        value => Value}
  end.

-spec delete_flag(ctx:t(), ffs_demo_pb:delete_flag_request()) ->
  {ok, ffs_demo_pb:delete_flag_response(), ctx:t()} | grpcbox_stream:grpc_error_response().
delete_flag(Ctx, #{name := Name}) ->
  Flag = 'Elixir.Featureflagservice.FeatureFlags':get_feature_flag_by_name(Name),
  case Flag of
    nil ->
      {grpc_error, {?GRPC_STATUS_NOT_FOUND, <<"the requested feature flag does not exist">>}};

    #{'__struct__' := 'Elixir.Featureflagservice.FeatureFlags.FeatureFlag'} ->
      'Elixir.Featureflagservice.FeatureFlags':delete_feature_flag(Flag),

      ?set_attribute('app.featureflag.name', Name),

      {ok, #{}, Ctx};

    _ ->
      {grpc_error, {?GRPC_STATUS_INTERNAL, <<"unexpected response from get_feature_flag_by_name">>}}
  end.
