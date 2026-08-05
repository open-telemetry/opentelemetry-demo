# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

defmodule FlagdUiWeb.Scheduler do
  use FlagdUiWeb, :live_view

  alias FlagdUiWeb.CoreComponents
  alias FlagdUiWeb.Components.Navbar

  @presets %{
    "presentation" => %{interval_seconds: 60, min_duration_seconds: 10, max_duration_seconds: 20},
    "hourly" => %{interval_seconds: 3600, min_duration_seconds: 300, max_duration_seconds: 900},
    "frequent" => %{interval_seconds: 900, min_duration_seconds: 60, max_duration_seconds: 180}
  }

  def mount(_, _, socket) do
    if connected?(socket) do
      Phoenix.PubSub.subscribe(FlagdUi.PubSub, FlagdUi.Scheduler.topic())
      Phoenix.PubSub.subscribe(FlagdUi.PubSub, FlagdUi.Storage.topic())
      :timer.send_interval(1000, self(), :tick)
    end

    scheduler = FlagdUi.Scheduler.state()
    available = available_flags()

    {:ok,
     socket
     |> assign(scheduler: scheduler)
     |> assign(available: available)
     |> assign(form: form_from(scheduler, available))
     |> assign(now: System.monotonic_time(:millisecond))
     |> assign(error: nil)}
  end

  def render(assigns) do
    ~H"""
    <div class="relative min-h-screen">
      <Navbar.navbar mode="scheduler" />

      <CoreComponents.flash kind={:error} flash={@flash} />
      <CoreComponents.flash kind={:info} flash={@flash} />

      <div class="container mx-auto px-4 py-8">
        <div class="mb-6 rounded-md bg-gray-800 p-6 text-gray-300 shadow-md">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-lg font-semibold">
                {if @scheduler.running, do: "Scheduler running", else: "Scheduler stopped"}
              </p>
              <p class="text-sm">
                Activates one randomly picked flag per interval, then turns it back off.
              </p>
            </div>
            <span class={[
              "rounded-full px-3 py-1 text-sm font-medium",
              @scheduler.running && "bg-green-700 text-white",
              !@scheduler.running && "bg-gray-700 text-gray-300"
            ]}>
              {if @scheduler.running, do: "Active", else: "Idle"}
            </span>
          </div>

          <dl :if={@scheduler.running} class="mt-4 grid grid-cols-1 gap-4 text-sm sm:grid-cols-3">
            <div>
              <dt class="font-medium text-gray-400">Interval</dt>
              <dd>{@scheduler.interval_count}</dd>
            </div>
            <div>
              <dt class="font-medium text-gray-400">Seed</dt>
              <dd>{@scheduler.seed_used}</dd>
            </div>
            <div>
              <dt class="font-medium text-gray-400">Currently active</dt>
              <dd>
                <%= if @scheduler.active do %>
                  <span class="text-warning">
                    {@scheduler.active.flag} = {@scheduler.active.variant}
                  </span>
                  <span class="text-gray-400">
                    ({format_ms(@scheduler.active.until - @now)} left)
                  </span>
                <% else %>
                  <span class="text-gray-400">
                    nothing &mdash; next in {next_trigger_label(@scheduler, @now)}
                  </span>
                <% end %>
              </dd>
            </div>
          </dl>
        </div>

        <p :if={@error} class="mb-4 rounded-md bg-red-900 p-4 text-sm text-white">{@error}</p>

        <.form id="scheduler-form" for={@form} phx-submit="start" phx-change="validate">
          <div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div class="rounded-md bg-gray-800 p-6 text-gray-300 shadow-md">
              <p class="mb-4 text-lg font-semibold">Timing</p>

              <CoreComponents.input
                name="interval_seconds"
                type="number"
                label="Interval (seconds)"
                value={@form["interval_seconds"]}
                min="1"
              />
              <CoreComponents.input
                name="min_duration_seconds"
                type="number"
                label="Minimum duration (seconds)"
                value={@form["min_duration_seconds"]}
                min="1"
              />
              <CoreComponents.input
                name="max_duration_seconds"
                type="number"
                label="Maximum duration (seconds)"
                value={@form["max_duration_seconds"]}
                min="1"
              />
              <CoreComponents.input
                name="seed"
                type="number"
                label="Seed (optional, for reproducible patterns)"
                value={@form["seed"]}
              />

              <div class="mt-4 flex flex-wrap gap-2">
                <button
                  :for={{name, label} <- preset_labels()}
                  type="button"
                  class="rounded bg-gray-700 px-3 py-2 text-xs font-medium text-gray-200 transition-colors duration-200 hover:bg-gray-600"
                  phx-click="preset"
                  phx-value-name={name}
                >
                  {label}
                </button>
              </div>
            </div>

            <div class="rounded-md bg-gray-800 p-6 text-gray-300 shadow-md">
              <div class="mb-4 flex items-center justify-between">
                <p class="text-lg font-semibold">Flags</p>
                <div class="flex gap-2">
                  <button
                    type="button"
                    class="rounded bg-gray-700 px-3 py-2 text-xs font-medium text-gray-200 transition-colors duration-200 hover:bg-gray-600"
                    phx-click="select_all"
                  >
                    All
                  </button>
                  <button
                    type="button"
                    class="rounded bg-gray-700 px-3 py-2 text-xs font-medium text-gray-200 transition-colors duration-200 hover:bg-gray-600"
                    phx-click="select_none"
                  >
                    None
                  </button>
                </div>
              </div>

              <p :if={@available == []} class="text-sm text-warning">
                No schedulable flags found in the current configuration.
              </p>

              <div class="max-h-96 overflow-y-auto">
                <label
                  :for={{name, variants} <- @available}
                  class="flex items-start gap-3 border-b border-gray-700 py-2 last:border-b-0"
                >
                  <input
                    type="checkbox"
                    name="flags[]"
                    value={name}
                    checked={name in @form["flags"]}
                    class="mt-1"
                  />
                  <span class="text-sm">
                    <span class="font-medium">{name}</span>
                    <span class="block text-xs text-gray-400">{Enum.join(variants, ", ")}</span>
                  </span>
                </label>
              </div>
            </div>
          </div>

          <div class="mt-6 flex gap-4">
            <button
              type="submit"
              class="rounded bg-blue-500 px-8 py-4 font-medium text-white transition-colors duration-200 hover:bg-blue-600"
            >
              {if @scheduler.running, do: "Restart", else: "Start"}
            </button>
            <button
              :if={@scheduler.running}
              type="button"
              class="rounded bg-red-600 px-8 py-4 font-medium text-white transition-colors duration-200 hover:bg-red-700"
              phx-click="stop"
            >
              Stop
            </button>
          </div>
        </.form>

        <div :if={@scheduler.history != []} class="mt-8 rounded-md bg-gray-800 p-6 text-gray-300">
          <p class="mb-4 text-lg font-semibold">Recent activations</p>
          <ul class="text-sm">
            <li
              :for={entry <- @scheduler.history}
              class="flex justify-between border-b border-gray-700 py-2 last:border-b-0"
            >
              <span>{entry.flag} = {entry.variant}</span>
              <span class="text-gray-400">
                {Calendar.strftime(entry.started_at, "%H:%M:%S UTC")} for {format_ms(
                  entry.duration_ms
                )}
              </span>
            </li>
          </ul>
        </div>
      </div>
    </div>
    """
  end

  def handle_event("validate", params, socket),
    do: {:noreply, assign(socket, form: merge_params(socket.assigns.form, params))}

  def handle_event("preset", %{"name" => name}, socket) do
    preset = Map.fetch!(@presets, name)

    form =
      Enum.reduce(preset, socket.assigns.form, fn {key, value}, form ->
        Map.put(form, Atom.to_string(key), value)
      end)

    {:noreply, assign(socket, form: form)}
  end

  def handle_event("select_all", _, socket) do
    names = Enum.map(socket.assigns.available, fn {name, _} -> name end)

    {:noreply, assign(socket, form: Map.put(socket.assigns.form, "flags", names))}
  end

  def handle_event("select_none", _, socket),
    do: {:noreply, assign(socket, form: Map.put(socket.assigns.form, "flags", []))}

  def handle_event("start", params, socket) do
    form = merge_params(socket.assigns.form, params)

    case build_config(form) do
      {:ok, config} ->
        case FlagdUi.Scheduler.start_schedule(config) do
          :ok ->
            {:noreply,
             socket
             |> assign(form: form, error: nil, scheduler: FlagdUi.Scheduler.state())
             |> clear_flash()
             |> put_flash(:info, "Scheduler started")}

          {:error, reason} ->
            {:noreply, assign(socket, form: form, error: reason)}
        end

      {:error, reason} ->
        {:noreply, assign(socket, form: form, error: reason)}
    end
  end

  def handle_event("stop", _, socket) do
    :ok = FlagdUi.Scheduler.stop_schedule()

    {:noreply,
     socket
     |> assign(error: nil, scheduler: FlagdUi.Scheduler.state())
     |> clear_flash()
     |> put_flash(:info, "Scheduler stopped")}
  end

  def handle_info({:scheduler_state, scheduler}, socket),
    do: {:noreply, assign(socket, scheduler: scheduler)}

  def handle_info({:flags_changed, _state}, socket),
    do: {:noreply, assign(socket, available: available_flags())}

  def handle_info(:tick, socket),
    do: {:noreply, assign(socket, now: System.monotonic_time(:millisecond))}

  defp available_flags do
    Storage
    |> GenServer.call(:read)
    |> FlagdUi.Scheduler.schedulable_flags()
  end

  defp form_from(scheduler, available) do
    config = scheduler.config

    selected =
      case config.flags do
        :all -> Enum.map(available, fn {name, _} -> name end)
        flags -> flags
      end

    %{
      "interval_seconds" => div(config.interval_ms, 1000),
      "min_duration_seconds" => div(config.min_duration_ms, 1000),
      "max_duration_seconds" => div(config.max_duration_ms, 1000),
      "seed" => config.seed,
      "flags" => selected
    }
  end

  defp merge_params(form, params) do
    form
    |> Map.merge(
      Map.take(params, ~w(interval_seconds min_duration_seconds max_duration_seconds seed))
    )
    |> Map.put("flags", Map.get(params, "flags", []))
  end

  defp build_config(form) do
    with {:ok, interval} <- parse_seconds(form["interval_seconds"], "Interval"),
         {:ok, min_duration} <- parse_seconds(form["min_duration_seconds"], "Minimum duration"),
         {:ok, max_duration} <- parse_seconds(form["max_duration_seconds"], "Maximum duration"),
         {:ok, seed} <- parse_seed(form["seed"]) do
      {:ok,
       %{
         interval_ms: interval * 1000,
         min_duration_ms: min_duration * 1000,
         max_duration_ms: max_duration * 1000,
         seed: seed,
         flags: form["flags"]
       }}
    end
  end

  defp parse_seconds(value, label) when is_integer(value), do: parse_seconds("#{value}", label)

  defp parse_seconds(value, label) when is_binary(value) do
    case Integer.parse(String.trim(value)) do
      {seconds, ""} when seconds > 0 -> {:ok, seconds}
      _ -> {:error, "#{label} must be a whole number of seconds greater than zero"}
    end
  end

  defp parse_seconds(_value, label), do: {:error, "#{label} is required"}

  defp parse_seed(nil), do: {:ok, nil}
  defp parse_seed(value) when is_integer(value), do: {:ok, value}

  defp parse_seed(value) when is_binary(value) do
    case String.trim(value) do
      "" ->
        {:ok, nil}

      trimmed ->
        case Integer.parse(trimmed) do
          {seed, ""} -> {:ok, seed}
          _ -> {:error, "Seed must be a whole number"}
        end
    end
  end

  defp next_trigger_label(%{next_trigger_at: nil}, _now), do: "unknown"
  defp next_trigger_label(%{next_trigger_at: at}, now), do: format_ms(at - now)

  defp format_ms(ms) when ms <= 0, do: "0s"

  defp format_ms(ms) do
    seconds = div(ms, 1000)
    minutes = div(seconds, 60)
    hours = div(minutes, 60)

    cond do
      hours > 0 -> "#{hours}h #{rem(minutes, 60)}m"
      minutes > 0 -> "#{minutes}m #{rem(seconds, 60)}s"
      true -> "#{seconds}s"
    end
  end

  defp preset_labels do
    [
      {"presentation", "Presentation (60s / 10-20s)"},
      {"frequent", "Frequent (15m / 1-3m)"},
      {"hourly", "Hourly (1h / 5-15m)"}
    ]
  end
end
