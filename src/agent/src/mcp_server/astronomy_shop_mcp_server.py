import logging
import os

from fastmcp import FastMCP
from src.agents import tools

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AstronomyShopMcp:
    def __init__(self) -> None:
        self.host = os.getenv("MCP_ENDPOINT", "127.0.0.1")
        self.port = int(os.getenv("MCP_PORT", "8011"))
        self.mcp = FastMCP("astronomy-shop-mcp")

        self._register_tools()

    def _register_tools(self):
        """Programmatically register static methods as MCP tools."""
        self.mcp.tool("add_to_cart")(tools.add_to_cart)
        self.mcp.tool("checkout")(tools.checkout)
        self.mcp.tool("convert_currency")(tools.convert_currency)
        self.mcp.tool("empty_cart")(tools.empty_cart)
        self.mcp.tool("get_ads")(tools.get_ads)
        self.mcp.tool("get_cart")(tools.get_cart)
        self.mcp.tool("get_product")(tools.get_product)
        self.mcp.tool("get_recommendations")(tools.get_recommendations)
        self.mcp.tool("get_shipping_quote")(tools.get_shipping_quote)
        self.mcp.tool("get_supported_currencies")(tools.get_supported_currencies)
        self.mcp.tool("list_products")(tools.list_products)

    def run(self):
        """Start the MCP server using http stream transport."""
        logger.info(f"Starting FastMCP Server on {self.host}:{self.port}")
        self.mcp.run(transport="http", host=self.host, port=self.port)
