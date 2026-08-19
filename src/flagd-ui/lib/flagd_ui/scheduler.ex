# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

defmodule FlagdUi.Scheduler do
  @moduledoc """
  Scheduler module. This module runs a GenServer that periodically activates
  randomly picked feature flags for a random amount of time, so that failure
  scenarios appear and disappear on their own without external tooling.

  Each interval activates up to `:concurrency` distinct flags. Every activation
  gets its own hold duration picked between the configured minimum and maximum,
  and its own offset, so that the whole activation fits inside the interval.
  Providing a seed makes the sequence of picks reproducible across runs.

  A flag is picked first and one of its selected variants second, so a flag with
  many variants is no more likely to be chosen than a flag with one.
  """

  use GenServer
  require Logger

  @topic "scheduler"

  @history_limit 10

  @default_config %{
    interval_ms: 15 * 60 * 1000,
    min_duration_ms: 60 * 1000,
    max_duration_ms: 3 * 60 * 1000,
    concurrency: 1,
    seed: nil,
    flags: :all
  }

  def start_link(opts) do
    name = Keyword.get(opts, :name, Scheduler)

    GenServer.start_link(__MODULE__, opts, name: name)
  end

  @doc "PubSub topic carrying scheduler state updates."
  def topic, do: @topic

  @doc "Default configuration used before the scheduler is first started."
  def default_config, do: @default_config

  @doc "Returns the scheduler state suitable for rendering."
  def state(server \\ Scheduler), do: GenServer.call(server, :state)

  @doc """
  Starts scheduling with the given configuration, replacing any run in progress.

  `:flags` is either `:all` or a map of flag name to the list of variants that
  may be activated, so that a flag can take part with only some of its variants.
  `:concurrency` is how many distinct flags may be activated per interval.
  Returns `{:error, reason}` when the configuration is not usable.
  """
  def start_schedule(server \\ Scheduler, config),
    do: GenServer.call(server, {:start_schedule, config})

  @doc "Stops scheduling and reverts any flag currently held active."
  def stop_schedule(server \\ Scheduler), do: GenServer.call(server, :stop_schedule)

  @doc """
  Returns the flags eligible for scheduling as `{name, activatable_variants}`
  pairs, given a flagd configuration.

  A flag is eligible when it has a resting variant, its configured default, to
  return to and at least one other variant to switch to.
  """
  def schedulable_flags(config) do
    config
    |> eligible_flag_specs()
    |> Enum.map(fn {name, _resting, activatable} -> {name, activatable} end)
  end

  defp eligible_flag_specs(%{"flags" => flags}) when is_map(flags) do
    flags
    |> Enum.flat_map(&flag_spec/1)
    |> Enum.sort()
  end

  defp eligible_flag_specs(_), do: []

  defp flag_spec({name, data}) do
    variants = variant_names(data)
    resting = Map.get(data, "defaultVariant")
    activatable = Enum.sort(variants -- [resting])

    if resting in variants and activatable != [] do
      [{name, resting, activatable}]
    else
      []
    end
  end

  @impl true
  def init(opts) do
    Process.flag(:trap_exit, true)

    {:ok,
     %{
       storage: Keyword.get(opts, :storage, Storage),
       config: @default_config,
       running: false,
       epoch: 0,
       rand: nil,
       seed_used: nil,
       interval_count: 0,
       next_up: [],
       active: %{},
       history: [],
       timers: %{},
       eligible: []
     }}
  end

  @impl true
  def handle_call(:state, _from, state), do: {:reply, public_state(state), state}

  @impl true
  def handle_call({:start_schedule, config}, _from, state) do
    config = Map.merge(@default_config, config)

    case validate(config) do
      :ok ->
        {seed, rand} = seed_rand(config.seed)
        state = state |> cancel_timers() |> revert_all()

        # Frozen for the run: the flags' own resting variants are read back from
        # storage as this run writes over them, so re-deriving mid-run would
        # mistake a flag's currently active variant for its rest state.
        eligible = state.storage |> GenServer.call(:read) |> eligible_flag_specs()

        new_state =
          state
          |> Map.merge(%{
            config: config,
            eligible: eligible,
            running: true,
            epoch: state.epoch + 1,
            rand: rand,
            seed_used: seed,
            interval_count: 0,
            history: []
          })
          |> begin_interval()

        Logger.info("Flag scheduler started with seed #{seed}")

        broadcast(new_state)

        {:reply, :ok, new_state}

      {:error, reason} ->
        {:reply, {:error, reason}, state}
    end
  end

  @impl true
  def handle_call(:stop_schedule, _from, state) do
    new_state =
      state
      |> cancel_timers()
      |> revert_all()
      |> Map.merge(%{running: false, epoch: state.epoch + 1, next_up: []})

    Logger.info("Flag scheduler stopped")

    broadcast(new_state)

    {:reply, :ok, new_state}
  end

  @impl true
  def handle_info({:begin_interval, epoch}, %{running: true, epoch: epoch} = state) do
    new_state = state |> drop_timer(:interval) |> begin_interval()

    broadcast(new_state)

    {:noreply, new_state}
  end

  @impl true
  def handle_info(
        {:trigger, epoch, flag, variant, resting_variant, duration_ms},
        %{running: true, epoch: epoch} = state
      ) do
    # The same flag can be picked again while a previous hold is still running,
    # so retire that activation before this one takes the flag over.
    state =
      state
      |> drop_timer({:trigger, flag})
      |> cancel_timer({:revert, flag})
      |> finish_activation(flag)

    GenServer.cast(state.storage, {:write, flag, variant})

    Logger.info("Flag scheduler set #{flag} to #{variant} for #{duration_ms}ms")

    revert_timer = Process.send_after(self(), {:revert, epoch, flag}, duration_ms)

    activation = %{
      flag: flag,
      variant: variant,
      resting_variant: resting_variant,
      duration_ms: duration_ms,
      started_at: DateTime.utc_now(),
      until: System.monotonic_time(:millisecond) + duration_ms
    }

    new_state =
      state
      |> put_timer({:revert, flag}, revert_timer)
      |> Map.update!(:active, &Map.put(&1, flag, activation))
      |> Map.update!(:next_up, fn pending -> Enum.reject(pending, &(&1.flag == flag)) end)

    broadcast(new_state)

    {:noreply, new_state}
  end

  @impl true
  def handle_info({:revert, epoch, flag}, %{running: true, epoch: epoch} = state) do
    new_state =
      state
      |> drop_timer({:revert, flag})
      |> revert_flag(flag)
      |> finish_activation(flag)

    broadcast(new_state)

    {:noreply, new_state}
  end

  @impl true
  def handle_info(_message, state), do: {:noreply, state}

  @impl true
  def terminate(_reason, state) do
    revert_all(state)

    :ok
  end

  defp begin_interval(%{config: config, epoch: epoch} = state) do
    interval_timer = Process.send_after(self(), {:begin_interval, epoch}, config.interval_ms)

    state =
      state
      |> put_timer(:interval, interval_timer)
      |> Map.update!(:interval_count, &(&1 + 1))

    flags = eligible_flags(state)
    wanted = min(config.concurrency, length(flags))

    if wanted == 0 do
      Logger.warning("Flag scheduler has no eligible flags selected, skipping interval")

      %{state | next_up: []}
    else
      log_shortfall(config.concurrency, wanted)

      {plans, rand} = plan_activations(flags, wanted, config, state.rand)

      Enum.reduce(plans, %{state | rand: rand, next_up: []}, &schedule_activation(&2, &1, epoch))
    end
  end

  defp log_shortfall(wanted, available) when wanted > available,
    do:
      Logger.warning(
        "Flag scheduler was asked for #{wanted} concurrent flags but only #{available} are selected"
      )

  defp log_shortfall(_wanted, _available), do: :ok

  defp schedule_activation(state, plan, epoch) do
    %{
      flag: flag,
      variant: variant,
      resting_variant: resting_variant,
      duration_ms: duration_ms,
      offset_ms: offset_ms
    } = plan

    timer =
      Process.send_after(
        self(),
        {:trigger, epoch, flag, variant, resting_variant, duration_ms},
        offset_ms
      )

    pending = %{
      flag: flag,
      variant: variant,
      duration_ms: duration_ms,
      at: System.monotonic_time(:millisecond) + offset_ms
    }

    state
    |> put_timer({:trigger, flag}, timer)
    |> Map.update!(:next_up, &(&1 ++ [pending]))
  end

  defp plan_activations(_flags, 0, _config, rand), do: {[], rand}
  defp plan_activations([], _wanted, _config, rand), do: {[], rand}

  defp plan_activations(flags, wanted, config, rand) do
    {{flag, resting_variant, variants} = picked, rand} = random_element(flags, rand)

    {duration_ms, rand} =
      random_in_range(config.min_duration_ms, config.max_duration_ms, rand)

    {offset_ms, rand} = random_in_range(0, config.interval_ms - duration_ms, rand)
    {variant, rand} = random_element(variants, rand)

    plan = %{
      flag: flag,
      variant: variant,
      resting_variant: resting_variant,
      duration_ms: duration_ms,
      offset_ms: offset_ms
    }

    {rest, rand} = plan_activations(List.delete(flags, picked), wanted - 1, config, rand)

    {[plan | rest], rand}
  end

  defp eligible_flags(%{eligible: eligible, config: %{flags: selection}}) do
    Enum.flat_map(eligible, fn {name, resting, variants} ->
      case select_variants(selection, name, variants) do
        [{^name, allowed}] -> [{name, resting, allowed}]
        [] -> []
      end
    end)
  end

  defp select_variants(:all, name, variants), do: [{name, variants}]

  defp select_variants(selection, name, variants) when is_map(selection) do
    chosen = Map.get(selection, name, [])

    case Enum.filter(variants, &(&1 in chosen)) do
      [] -> []
      allowed -> [{name, allowed}]
    end
  end

  defp revert_all(state) do
    state.active
    |> Map.keys()
    |> Enum.reduce(state, fn flag, acc ->
      acc |> revert_flag(flag) |> finish_activation(flag)
    end)
  end

  defp revert_flag(%{storage: storage, active: active} = state, flag) do
    variant = active |> Map.fetch!(flag) |> Map.fetch!(:resting_variant)

    GenServer.cast(storage, {:write, flag, variant})

    Logger.info("Flag scheduler reverted #{flag} to #{variant}")

    state
  end

  defp finish_activation(state, flag) do
    case Map.pop(state.active, flag) do
      {nil, _active} ->
        state

      {activation, active} ->
        %{
          state
          | active: active,
            history: Enum.take([activation | state.history], @history_limit)
        }
    end
  end

  defp validate(config) do
    cond do
      config.interval_ms < 1000 ->
        {:error, "Interval must be at least 1 second"}

      config.min_duration_ms < 1000 ->
        {:error, "Minimum duration must be at least 1 second"}

      config.max_duration_ms < config.min_duration_ms ->
        {:error, "Maximum duration must be greater than or equal to the minimum duration"}

      config.max_duration_ms > config.interval_ms ->
        {:error, "Maximum duration must fit within the interval"}

      config.concurrency < 1 ->
        {:error, "At least one flag has to be activated per interval"}

      config.flags != :all and selected_variant_count(config.flags) == 0 ->
        {:error, "Select at least one flag variant to schedule"}

      true ->
        :ok
    end
  end

  defp selected_variant_count(selection) when is_map(selection),
    do: selection |> Map.values() |> Enum.map(&length/1) |> Enum.sum()

  defp selected_variant_count(_selection), do: 0

  defp seed_rand(nil) do
    seed = :erlang.unique_integer([:positive])

    seed_rand(seed)
  end

  defp seed_rand(seed) when is_integer(seed), do: {seed, :rand.seed_s(:exsss, {seed, seed, seed})}

  defp random_element(list, rand) do
    {index, rand} = :rand.uniform_s(length(list), rand)

    {Enum.at(list, index - 1), rand}
  end

  defp random_in_range(min, max, rand) when max > min do
    {offset, rand} = :rand.uniform_s(max - min + 1, rand)

    {min + offset - 1, rand}
  end

  defp random_in_range(min, _max, rand), do: {min, rand}

  defp put_timer(state, key, ref), do: Map.update!(state, :timers, &Map.put(&1, key, ref))

  defp drop_timer(state, key), do: Map.update!(state, :timers, &Map.delete(&1, key))

  defp cancel_timers(state) do
    Enum.each(state.timers, fn {_key, ref} -> Process.cancel_timer(ref) end)

    %{state | timers: %{}}
  end

  defp cancel_timer(state, key) do
    case Map.fetch(state.timers, key) do
      {:ok, ref} ->
        Process.cancel_timer(ref)

        drop_timer(state, key)

      :error ->
        state
    end
  end

  defp variant_names(%{"variants" => variants}) when is_map(variants), do: Map.keys(variants)
  defp variant_names(_), do: []

  defp public_state(state) do
    state
    |> Map.take([
      :config,
      :running,
      :seed_used,
      :interval_count,
      :next_up,
      :history
    ])
    |> Map.put(:active, state.active |> Map.values() |> Enum.sort_by(& &1.flag))
    |> Map.put(:next_trigger_at, next_trigger_at(state.next_up))
  end

  defp next_trigger_at([]), do: nil
  defp next_trigger_at(pending), do: pending |> Enum.map(& &1.at) |> Enum.min()

  defp broadcast(state) do
    Phoenix.PubSub.broadcast(FlagdUi.PubSub, @topic, {:scheduler_state, public_state(state)})
  end
end
