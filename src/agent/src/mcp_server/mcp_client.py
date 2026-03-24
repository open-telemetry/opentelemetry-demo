from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


class MCPClient:
    def __init__(self):
        self.exit_stack = AsyncExitStack()
        self.session = None

    async def connect_to_mcp_server(self, url):
        stream_context = streamablehttp_client(url=url)
        read, write, _ = await self.exit_stack.enter_async_context(stream_context)
        session_context = ClientSession(read, write)
        self.session = await self.exit_stack.enter_async_context(session_context)
        await self.session.initialize()

    async def cleanup(self):
        try:
            await self.exit_stack.aclose()
        except Exception as e:
            print(f"Error closing connection : {e}")
