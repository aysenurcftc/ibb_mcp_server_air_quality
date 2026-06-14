import asyncio
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastmcp import FastMCP

from .adapters.ibb_air_quality import IBBAirQualityAdapter
from .cache.redis_cache import RedisCache
from .tool.air_quality_tools import register_air_quality_tools

load_dotenv()


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_TTL = int(os.getenv("CACHE_TTL", "60"))
IBB_BASE_URL = os.getenv(
    "IBB_HAVA_KALITESI_BASE_URL",
    "https://api.ibb.gov.tr/havakalitesi/OpenDataPortalHandler",
)


@asynccontextmanager
async def app_lifespan(server: FastMCP):
    """Initialize adapters and cache on server startup, and clean up on shutdown."""
    logger.info("Starting IBB MCP Server...")

    cache = RedisCache(redis_url=REDIS_URL, default_ttl=CACHE_TTL)

    await cache.connect()
    adapter = IBBAirQualityAdapter(base_url=IBB_BASE_URL)
    await adapter.connect()

    register_air_quality_tools(server, adapter, cache)

    logger.info("✅ All adapters and tools are ready.")

    try:
        yield
    finally:
        logger.info("Stopping Server...")
        await adapter.disconnect()
        await cache.disconnect()
        logger.info("Connections closed.")


mcp = FastMCP(
    name="ibb-mcp-server",
    instructions="""
    MCP server providing access to the IBB (İstanbul Büyükşehir Belediyesi) Open Data APIs.
    Available tools:
    - get_air_quality_stations: Retrieves all air quality monitoring stations in Istanbul.
    - get_air_quality_measurements: Retrieves measurement data for a specific station and date range.
    - get_station_latest_status: Retrieves the status of a station over the last 24 hours.
    - air_quality_health_check: Checks API and cache connection status.

    Note:
        Data is cached for 60 seconds (Redis) to mitigate the risk of IP banning.
    """,
    lifespan=app_lifespan,
)


def main():
    """CLI entry point: Executed via the `ibb-mcp` command."""
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8000"))

    logger.info(f"Transport: {transport}")

    if transport == "stdio":
        mcp.run(transport="stdio")
    elif transport == "http":
        mcp.run(transport="http", host=host, port=port)
    else:
        logger.error(f"Invalid transport: {transport}. Use 'stdio' or 'http'.")


if __name__ == "__main__":
    main()
