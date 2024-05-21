defmodule ChatServiceWeb.PageController do
  use ChatServiceWeb, :controller

  def home(conn, _params) do
    topics = ChatService.ChatServer.list_topics()

    assigns = [
      topics: topics
    ]

    render(conn, :home, assigns)
  end
end
