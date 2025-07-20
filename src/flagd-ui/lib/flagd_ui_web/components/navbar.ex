defmodule FlagdUiWeb.Components.Navbar do
  use FlagdUiWeb, :live_view

  def navbar(assigns) do
    ~H"""
    <nav class="bg-gray-800 p-4 sm:p-6">
      <div class="container mx-auto flex items-center justify-between">
        <a href="/" class="text-xl font-bold text-white">
          Flagd Configurator
        </a>
        <ul class="flex space-x-2 sm:space-x-4">
          <li>
            <a
              href="/"
              class="rounded-md px-3 py-2 text-sm font-medium bg-blue-700 text-white underline underline-offset-4 transition-all duration-200"
            >
              Basic
            </a>
          </li>
          <li>
            <a
              href="/advanced"
              class="rounded-md px-3 py-2 text-sm font-medium text-gray-300 hover:bg-gray-700 hover:text-white transition-all duration-200"
            >
              Advanced
            </a>
          </li>
        </ul>
      </div>
    </nav>
    """
  end
end
