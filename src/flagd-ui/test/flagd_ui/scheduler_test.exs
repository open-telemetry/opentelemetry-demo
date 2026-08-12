# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

defmodule FlagdUi.SchedulerTest do
  use ExUnit.Case

  alias FlagdUi.Scheduler

  setup do
    original = GenServer.call(Storage, :read)

    on_exit(fn ->
      GenServer.cast(Storage, {:replace, Jason.encode!(original)})
    end)

    :ok
  end

  # Every activation is held for the whole interval, so the offset within the
  # interval is always zero. That leaves the flag and variant picks as the only
  # consumers of randomness, which keeps seeded runs comparable.
  defp immediate_config(overrides \\ %{}) do
    Map.merge(
      %{interval_ms: 1000, min_duration_ms: 1000, max_duration_ms: 1000, seed: 42, flags: :all},
      overrides
    )
  end

  defp start_scheduler(name) do
    {:ok, _pid} = start_supervised({Scheduler, [name: name, storage: Storage]}, id: name)

    name
  end

  # Mirrors Storage.update_flag/3: a flag with a 3-element targeting.if
  # (condition, on-value, off-value) is toggled through that rule rather than
  # its defaultVariant, e.g. productCatalogFailure.
  defp variant_of(flag) do
    data = get_in(GenServer.call(Storage, :read), ["flags", flag])

    case get_in(data, ["targeting", "if"]) do
      [_condition, on_value, _off_value] -> on_value
      _ -> Map.get(data, "defaultVariant")
    end
  end

  defp eventually(fun, timeout \\ 3000) do
    deadline = System.monotonic_time(:millisecond) + timeout

    do_eventually(fun, deadline)
  end

  defp do_eventually(fun, deadline) do
    cond do
      fun.() ->
        true

      System.monotonic_time(:millisecond) >= deadline ->
        false

      true ->
        Process.sleep(50)
        do_eventually(fun, deadline)
    end
  end

  describe "schedulable_flags/1" do
    test "offers every failure flag with its non-off variants" do
      flags = Storage |> GenServer.call(:read) |> Scheduler.schedulable_flags()

      assert {"adFailure", ["on"]} in flags
      assert {"imageSlowLoad", ["10sec", "5sec"]} in flags

      assert {"cartFailure", ["10%", "100%", "25%", "50%", "75%", "90%"]} in flags
    end

    test "offers loadGeneratorTraffic, whose resting state is on" do
      flags = Storage |> GenServer.call(:read) |> Scheduler.schedulable_flags()

      assert {"loadGeneratorTraffic", ["off"]} in flags
    end

    test "offers loadGeneratorVUs, whose resting state is its default variant" do
      flags = Storage |> GenServer.call(:read) |> Scheduler.schedulable_flags()

      assert {"loadGeneratorVUs", ["10", "25", "50"]} in flags
    end

    test "tolerates a configuration without flags" do
      assert Scheduler.schedulable_flags(%{}) == []
      assert Scheduler.schedulable_flags(%{"flags" => nil}) == []
    end
  end

  describe "start_schedule/2 validation" do
    setup do
      {:ok, scheduler: start_scheduler(ValidationScheduler)}
    end

    test "rejects an interval below one second", %{scheduler: scheduler} do
      config = immediate_config(%{interval_ms: 500})

      assert {:error, message} = Scheduler.start_schedule(scheduler, config)
      assert message =~ "Interval must be at least 1 second"
    end

    test "rejects a maximum duration below the minimum", %{scheduler: scheduler} do
      config = immediate_config(%{min_duration_ms: 5000, max_duration_ms: 2000})

      assert {:error, message} = Scheduler.start_schedule(scheduler, config)
      assert message =~ "greater than or equal to the minimum"
    end

    test "rejects a duration that cannot fit inside the interval", %{scheduler: scheduler} do
      config = immediate_config(%{interval_ms: 2000, max_duration_ms: 5000})

      assert {:error, message} = Scheduler.start_schedule(scheduler, config)
      assert message =~ "must fit within the interval"
    end

    test "rejects an empty flag selection", %{scheduler: scheduler} do
      assert {:error, message} =
               Scheduler.start_schedule(scheduler, immediate_config(%{flags: %{}}))

      assert message =~ "at least one flag variant"
    end

    test "rejects a selection where every flag has no variants", %{scheduler: scheduler} do
      config = immediate_config(%{flags: %{"adFailure" => [], "cartFailure" => []}})

      assert {:error, message} = Scheduler.start_schedule(scheduler, config)
      assert message =~ "at least one flag variant"
    end

    test "leaves the scheduler stopped after a rejected configuration", %{scheduler: scheduler} do
      Scheduler.start_schedule(scheduler, immediate_config(%{interval_ms: 500}))

      refute Scheduler.state(scheduler).running
    end
  end

  describe "running the schedule" do
    setup do
      Phoenix.PubSub.subscribe(FlagdUi.PubSub, Scheduler.topic())

      :ok
    end

    test "activates a flag and reports it as active" do
      scheduler = start_scheduler(ActivationScheduler)

      assert :ok = Scheduler.start_schedule(scheduler, immediate_config())

      assert_receive {:scheduler_state, %{active: [%{flag: flag, variant: variant}]}}, 2000

      assert flag in Enum.map(
               Storage |> GenServer.call(:read) |> Scheduler.schedulable_flags(),
               fn {name, _} -> name end
             )

      assert variant != "off"
      assert eventually(fn -> variant_of(flag) == variant end)
    end

    test "turns the flag back off when the hold expires" do
      scheduler = start_scheduler(RevertScheduler)

      config =
        immediate_config(%{interval_ms: 5000, min_duration_ms: 1000, max_duration_ms: 1000})

      assert :ok = Scheduler.start_schedule(scheduler, config)

      assert_receive {:scheduler_state, %{active: [%{flag: flag}]}}, 5000

      assert eventually(fn -> variant_of(flag) == "off" end, 2000)
      assert Enum.any?(Scheduler.state(scheduler).history, &(&1.flag == flag))
    end

    test "reverts loadGeneratorTraffic to on, not off" do
      scheduler = start_scheduler(TrafficRevertScheduler)

      config = immediate_config(%{flags: %{"loadGeneratorTraffic" => ["off"]}})

      assert :ok = Scheduler.start_schedule(scheduler, config)

      assert_receive {:scheduler_state, %{active: [%{flag: "loadGeneratorTraffic"}]}}, 2000
      assert eventually(fn -> variant_of("loadGeneratorTraffic") == "off" end)

      assert :ok = Scheduler.stop_schedule(scheduler)

      assert eventually(fn -> variant_of("loadGeneratorTraffic") == "on" end)
    end

    test "reverts loadGeneratorVUs to its own default, not off" do
      scheduler = start_scheduler(VUsRevertScheduler)

      config = immediate_config(%{flags: %{"loadGeneratorVUs" => ["25"]}})

      assert :ok = Scheduler.start_schedule(scheduler, config)

      assert_receive {:scheduler_state, %{active: [%{flag: "loadGeneratorVUs", variant: "25"}]}},
                     2000

      assert :ok = Scheduler.stop_schedule(scheduler)

      assert eventually(fn -> variant_of("loadGeneratorVUs") == "5" end)
    end

    test "reverts every flag it activates when holds fill the whole interval" do
      scheduler = start_scheduler(BackToBackScheduler)

      # Restrict to off-resting flags: loadGeneratorTraffic and loadGeneratorVUs
      # rest elsewhere and are covered by their own revert tests above.
      selection =
        Storage
        |> GenServer.call(:read)
        |> Scheduler.schedulable_flags()
        |> Enum.reject(fn {name, _} -> name in ["loadGeneratorTraffic", "loadGeneratorVUs"] end)
        |> Map.new()

      # A hold as long as the interval makes each revert land exactly on the next
      # interval boundary, which previously left the earlier flag switched on.
      assert :ok =
               Scheduler.start_schedule(scheduler, immediate_config(%{seed: 99, flags: selection}))

      assert_receive {:scheduler_state, %{active: [%{flag: _}]}}, 2000

      Process.sleep(3500)

      assert :ok = Scheduler.stop_schedule(scheduler)

      state = Scheduler.state(scheduler)
      touched = state.history |> Enum.map(& &1.flag) |> Enum.uniq()

      # More than one activation means an interval boundary was crossed, which is
      # where the stranded flag used to appear.
      assert length(touched) > 1
      assert state.active == []

      for flag <- touched do
        assert eventually(fn -> variant_of(flag) == "off" end)
      end
    end

    test "stopping reverts a flag that is still active" do
      scheduler = start_scheduler(StopScheduler)

      assert :ok =
               Scheduler.start_schedule(
                 scheduler,
                 immediate_config(%{
                   interval_ms: 60_000,
                   max_duration_ms: 60_000,
                   min_duration_ms: 60_000
                 })
               )

      assert_receive {:scheduler_state, %{active: [%{flag: flag}]}}, 2000

      assert :ok = Scheduler.stop_schedule(scheduler)

      state = Scheduler.state(scheduler)

      refute state.running
      assert state.active == []
      assert eventually(fn -> variant_of(flag) == "off" end)
    end

    test "restricts activations to the selected flags" do
      scheduler = start_scheduler(SelectionScheduler)

      config = immediate_config(%{flags: %{"adHighCpu" => ["on"]}})

      assert :ok = Scheduler.start_schedule(scheduler, config)

      assert_receive {:scheduler_state, %{active: [%{flag: "adHighCpu", variant: "on"}]}}, 2000
    end

    test "restricts activations to the selected variants of a flag" do
      scheduler = start_scheduler(VariantSelectionScheduler)

      config = immediate_config(%{flags: %{"cartFailure" => ["10%", "25%"]}})

      assert :ok = Scheduler.start_schedule(scheduler, config)

      for _ <- 1..4 do
        assert_receive {:scheduler_state, %{active: [%{flag: "cartFailure", variant: variant}]}},
                       2000

        assert variant in ["10%", "25%"]
      end
    end

    test "ignores selected variants a flag no longer offers" do
      scheduler = start_scheduler(StaleVariantScheduler)

      config = immediate_config(%{flags: %{"adFailure" => ["on"], "cartFailure" => ["200%"]}})

      assert :ok = Scheduler.start_schedule(scheduler, config)

      assert_receive {:scheduler_state, %{active: [%{flag: "adFailure", variant: "on"}]}}, 2000
    end

    test "the same seed picks the same flag and variant" do
      first = start_scheduler(SeedSchedulerA)

      assert :ok = Scheduler.start_schedule(first, immediate_config(%{seed: 1234}))
      assert_receive {:scheduler_state, %{active: [%{flag: flag, variant: variant}]}}, 2000
      assert :ok = Scheduler.stop_schedule(first)

      second = start_scheduler(SeedSchedulerB)

      assert :ok = Scheduler.start_schedule(second, immediate_config(%{seed: 1234}))
      assert_receive {:scheduler_state, %{active: [%{flag: ^flag, variant: ^variant}]}}, 2000
      assert :ok = Scheduler.stop_schedule(second)
    end

    # A hold as long as the interval keeps every activation in place for the
    # whole test, so concurrent holds can be observed without racing a revert.
    defp held_config(overrides) do
      immediate_config(
        Map.merge(
          %{interval_ms: 60_000, min_duration_ms: 60_000, max_duration_ms: 60_000},
          overrides
        )
      )
    end

    test "holds several distinct flags active at once" do
      scheduler = start_scheduler(ConcurrentScheduler)

      assert :ok = Scheduler.start_schedule(scheduler, held_config(%{concurrency: 3}))

      assert_receive {:scheduler_state, %{active: [_, _, _] = active}}, 2000

      flags = Enum.map(active, & &1.flag)

      assert length(Enum.uniq(flags)) == 3

      for flag <- flags do
        assert eventually(fn -> variant_of(flag) != "off" end)
      end
    end

    test "never activates the same flag twice within an interval" do
      scheduler = start_scheduler(DistinctScheduler)

      assert :ok = Scheduler.start_schedule(scheduler, held_config(%{concurrency: 5}))

      state = Scheduler.state(scheduler)
      flags = Enum.map(state.next_up, & &1.flag) ++ Enum.map(state.active, & &1.flag)

      assert length(flags) == 5
      assert length(Enum.uniq(flags)) == 5
    end

    test "asks for more concurrency than there are flags and settles for what exists" do
      scheduler = start_scheduler(OverAskScheduler)

      config = held_config(%{concurrency: 99, flags: %{"adFailure" => ["on"]}})

      assert :ok = Scheduler.start_schedule(scheduler, config)

      assert_receive {:scheduler_state, %{active: [%{flag: "adFailure"}]}}, 2000
    end

    test "reverts every concurrently held flag when stopped" do
      scheduler = start_scheduler(ConcurrentStopScheduler)

      assert :ok = Scheduler.start_schedule(scheduler, held_config(%{concurrency: 4}))

      assert_receive {:scheduler_state, %{active: [_, _, _, _] = active}}, 2000

      flags = Enum.map(active, & &1.flag)

      assert :ok = Scheduler.stop_schedule(scheduler)

      assert Scheduler.state(scheduler).active == []

      for flag <- flags do
        assert eventually(fn -> variant_of(flag) == "off" end)
      end
    end

    test "rejects a concurrency below one" do
      scheduler = start_scheduler(BadConcurrencyScheduler)

      assert {:error, message} =
               Scheduler.start_schedule(scheduler, immediate_config(%{concurrency: 0}))

      assert message =~ "At least one flag has to be activated"
    end

    test "reports the seed it used when none was given" do
      scheduler = start_scheduler(RandomSeedScheduler)

      assert :ok = Scheduler.start_schedule(scheduler, immediate_config(%{seed: nil}))

      assert is_integer(Scheduler.state(scheduler).seed_used)
    end
  end
end
