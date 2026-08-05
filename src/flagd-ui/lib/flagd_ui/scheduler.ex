# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

defmodule FlagdUi.Scheduler do
  @moduledoc """
  Scheduler module. This module runs a GenServer that periodically activates a
  randomly picked feature flag for a random amount of time, so that failure
  scenarios appear and disappear on their own without external tooling.

  Each interval activates at most one flag. A hold duration is picked between
  the configured minimum and maximum, then an offset is picked so that the whole
  activation fits inside the interval. Providing a seed makes the sequence of
  picks reproducible across runs.

  A flag is picked first and one of its selected variants second, so a flag with
  many variants is no more likely to be chosen than a flag with one.
  """

  use GenServer
  require Logger

  @topic "scheduler"

  # "off" is not the resting state of loadGeneratorTraffic: the demo expects it
  # enabled, and toggling it would stop all synthetic traffic.
  @excluded_flags ["loadGeneratorTraffic"]

  @resting_variant "off"

  @history_limit 10

  @default_config %{
    interval_ms: 15 * 60 * 1000,
    min_duration_ms: 60 * 1000,
    max_duration_ms: 3 * 60 * 1000,
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
  Returns `{:error, reason}` when the configuration is not usable.
  """
  def start_schedule(server \\ Scheduler, config),
    do: GenServer.call(server, {:start_schedule, config})

  @doc "Stops scheduling and reverts any flag currently held active."
  def stop_schedule(server \\ Scheduler), do: GenServer.call(server, :stop_schedule)

  @doc """
  Returns the flags eligible for scheduling as `{name, activatable_variants}`
  pairs, given a flagd configuration.

  A flag is eligible when it has an "off" variant to return to and at least one
  other variant to switch to. That excludes flags such as `loadGeneratorVUs`,
  which is a tuning knob rather than a failure scenario.
  """
  def schedulable_flags(%{"flags" => flags}) when is_map(flags) do
    flags
    |> Enum.flat_map(&schedulable_flag/1)
    |> Enum.sort()
  end

  def schedulable_flags(_), do: []

  defp schedulable_flag({name, _data}) when name in @excluded_flags, do: []

  defp schedulable_flag({name, data}) do
    variants = variant_names(data)
    activatable = Enum.sort(variants -- [@resting_variant])

    if @resting_variant in variants and activatable != [] do
      [{name, activatable}]
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
       next_trigger_at: nil,
       next_up: nil,
       active: nil,
       history: [],
       timers: %{}
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

        new_state =
          state
          |> cancel_timers()
          |> clear_active()
          |> Map.merge(%{
            config: config,
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
      |> clear_active()
      |> Map.merge(%{
        running: false,
        epoch: state.epoch + 1,
        next_trigger_at: nil,
        next_up: nil
      })

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
        {:trigger, epoch, flag, variant, duration_ms},
        %{running: true, epoch: epoch} = state
      ) do
    # A hold that fills the whole interval expires as the next one begins, and
    # the two timers can be processed in either order, so retire any activation
    # still on the books before taking over.
    state = state |> cancel_timer(:revert) |> clear_active()

    GenServer.cast(state.storage, {:write, flag, variant})

    Logger.info("Flag scheduler set #{flag} to #{variant} for #{duration_ms}ms")

    revert_timer = Process.send_after(self(), {:revert, epoch, flag}, duration_ms)

    new_state =
      state
      |> drop_timer(:trigger)
      |> put_timer(:revert, revert_timer)
      |> Map.merge(%{
        next_trigger_at: nil,
        next_up: nil,
        active: %{
          flag: flag,
          variant: variant,
          duration_ms: duration_ms,
          started_at: DateTime.utc_now(),
          until: System.monotonic_time(:millisecond) + duration_ms
        }
      })

    broadcast(new_state)

    {:noreply, new_state}
  end

  @impl true
  def handle_info({:revert, epoch, flag}, %{running: true, epoch: epoch} = state) do
    new_state = state |> drop_timer(:revert) |> revert_flag(flag) |> finish_activation(flag)

    broadcast(new_state)

    {:noreply, new_state}
  end

  @impl true
  def handle_info(_message, state), do: {:noreply, state}

  @impl true
  def terminate(_reason, state) do
    clear_active(state)

    :ok
  end

  defp begin_interval(%{config: config, epoch: epoch} = state) do
    interval_timer = Process.send_after(self(), {:begin_interval, epoch}, config.interval_ms)

    state =
      state
      |> put_timer(:interval, interval_timer)
      |> Map.update!(:interval_count, &(&1 + 1))

    case eligible_flags(state) do
      [] ->
        Logger.warning("Flag scheduler has no eligible flags selected, skipping interval")

        %{state | next_trigger_at: nil, next_up: nil}

      flags ->
        {duration_ms, rand} =
          random_in_range(config.min_duration_ms, config.max_duration_ms, state.rand)

        {offset_ms, rand} = random_in_range(0, config.interval_ms - duration_ms, rand)
        {{flag, variants}, rand} = random_element(flags, rand)
        {variant, rand} = random_element(variants, rand)

        trigger_timer =
          Process.send_after(self(), {:trigger, epoch, flag, variant, duration_ms}, offset_ms)

        state
        |> put_timer(:trigger, trigger_timer)
        |> Map.merge(%{
          rand: rand,
          next_trigger_at: System.monotonic_time(:millisecond) + offset_ms,
          next_up: %{flag: flag, variant: variant, duration_ms: duration_ms}
        })
    end
  end

  defp eligible_flags(%{storage: storage, config: %{flags: selection}}) do
    storage
    |> GenServer.call(:read)
    |> schedulable_flags()
    |> Enum.flat_map(fn {name, variants} -> select_variants(selection, name, variants) end)
  end

  defp select_variants(:all, name, variants), do: [{name, variants}]

  defp select_variants(selection, name, variants) when is_map(selection) do
    chosen = Map.get(selection, name, [])

    case Enum.filter(variants, &(&1 in chosen)) do
      [] -> []
      allowed -> [{name, allowed}]
    end
  end

  defp clear_active(%{active: nil} = state), do: state

  defp clear_active(%{active: active} = state) do
    state |> revert_flag(active.flag) |> finish_activation(active.flag)
  end

  defp revert_flag(%{storage: storage} = state, flag) do
    GenServer.cast(storage, {:write, flag, @resting_variant})

    Logger.info("Flag scheduler reverted #{flag} to #{@resting_variant}")

    state
  end

  defp finish_activation(%{active: %{flag: flag} = active} = state, flag) do
    %{state | active: nil, history: Enum.take([active | state.history], @history_limit)}
  end

  defp finish_activation(state, _flag), do: state

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

  defp put_timer(state, key, ref), do: put_in(state, [:timers, key], ref)

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
    Map.take(state, [
      :config,
      :running,
      :seed_used,
      :interval_count,
      :next_trigger_at,
      :next_up,
      :active,
      :history
    ])
  end

  defp broadcast(state) do
    Phoenix.PubSub.broadcast(FlagdUi.PubSub, @topic, {:scheduler_state, public_state(state)})
  end
end
