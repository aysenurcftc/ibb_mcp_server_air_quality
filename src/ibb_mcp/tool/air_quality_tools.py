import logging
from datetime import datetime, timedelta
from ..adapters.ibb_air_quality import IBBAirQualityAdapter
from ..cache.redis_cache import RedisCache
from ..models import MCPResponse
from typing import Any

logger = logging.getLogger(__name__)


def register_air_quality_tools(mcp, adapter: IBBAirQualityAdapter, cache: RedisCache):
    """
    Register air quality tools to the MCP server.

    Args:
        mcp: FastMCP server instance
        adapter: IBB adapter
        cache: Redis cache manager
    """

    @mcp.tool()
    async def get_air_quality_stations() -> Any:
        """
        Returns a list of all air quality measuring stations in Istanbul.
        Includes the name, address, and coordinates of each station.
        Results are cached for 60 seconds.
        """
        cache_key = cache.make_key("station", "all")

        cached = await cache.get(cache_key)
        if cached:
            return MCPResponse(
                success=True,
                data=cached,
                cached=True,
                source=adapter.SOURCE_NAME,
                extra={"count": len(cached)},
            ).to_dict()

        try:
            stations = await adapter.get_stations()
            data = [s.to_dict() for s in stations]
            await cache.set(cache_key, data, ttl=60)

            return MCPResponse(
                success=True,
                data=data,
                cached=False,
                source=adapter.SOURCE_NAME,
                extra={"count": len(data)},
            ).to_dict()
        except Exception as e:
            logger.error(f"Failed to retrieve station list: {e}")
            return MCPResponse(
                success=False,
                data=None,
                error=f"Failed to retrieve station list: {str(e)}",
                source=adapter.SOURCE_NAME,
            ).to_dict()

    @mcp.tool()
    async def get_air_quality_measurements(
        station_id: str,
        start_date: str,
        end_date: str,
    ) -> Any:
        """
        Returns the measurement data for the specified air quality station.
        Provides PM10, SO2, O3, NO2, and CO values both as concentration and AQI.

        Args:
            station_id: Station UUID (retrieved via get_air_quality_stations)
            start_date: Start date (in YYYY-MM-DD format, e.g., 2024-01-15)
            end_date: End date (in YYYY-MM-DD format, e.g., 2024-01-16)
        """
        try:
            # Fixed: datetime.strtime -> datetime.strptime
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError as e:
            return MCPResponse(
                success=False,
                data=None,
                error=f"Invalid date format. Use YYYY-MM-DD. Error: {e}",
                source=adapter.SOURCE_NAME,
            ).to_dict()

        if (end_dt - start_dt).days > 7:
            return MCPResponse(
                success=False,
                data=None,
                error="Data can be queried for a maximum of 7 days.",
                source=adapter.SOURCE_NAME,
            ).to_dict()

        cache_key = cache.make_key("measurements", station_id, start_date, end_date)

        cached = await cache.get(cache_key)
        if cached:
            return MCPResponse(
                success=True,
                data=cached,
                cached=True,
                source=adapter.SOURCE_NAME,
                extra={"count": len(cached), "station_id": station_id},
            ).to_dict()

        try:
            measurements = await adapter.get_measurements(station_id, start_dt, end_dt)
            data = [m.to_dict() for m in measurements]

            await cache.set(cache_key, data, ttl=60)

            return MCPResponse(
                success=True,
                data=data,
                cached=False,
                source=adapter.SOURCE_NAME,
                extra={"count": len(data), "station_id": station_id},
            ).to_dict()
        except Exception as e:
            logger.error(f"Failed to retrieve measurement data [{station_id}]: {e}")
            return MCPResponse(
                success=False,
                data=None,
                error=f"Failed to retrieve measurement data: {str(e)}",
                source=adapter.SOURCE_NAME,
            ).to_dict()

    @mcp.tool()
    async def get_station_latest_status(station_id: str) -> Any:
        """
        Shows a summary of the latest air quality status for a station today.
        Returns the station name, AQI value, dominant pollutant, and status color.

        Args:
            station_id: Station UUID
        """
        cache_key = cache.make_key("latest", station_id)
        cached = await cache.get(cache_key)

        if cached:
            return MCPResponse(
                success=True, data=cached, cached=True, source=adapter.SOURCE_NAME
            ).to_dict()

        try:
            now = datetime.now()
            yesterday = now - timedelta(days=1)
            measurements = await adapter.get_measurements(station_id, yesterday, now)

            if not measurements:
                return MCPResponse(
                    success=False,
                    data=None,
                    error="No measurements found for this station in the last 24 hours.",
                    source=adapter.SOURCE_NAME,
                ).to_dict()

            latest = max(measurements, key=lambda m: m.read_time)
            data = {
                "station_id": station_id,
                "read_time": latest.read_time.isoformat(),
                "aqi_summary": latest.aqi.to_dict(),
                "concentration_summary": latest.concentration.to_dict(),
            }
            await cache.set(cache_key, data, ttl=60)
            return MCPResponse(
                success=True, data=data, cached=False, source=adapter.SOURCE_NAME
            ).to_dict()
        except Exception as e:
            logger.error(f"Failed to retrieve latest status [{station_id}]: {e}")
            return MCPResponse(
                success=False,
                data=None,
                error=str(e),
                source=adapter.SOURCE_NAME,
            ).to_dict()

    @mcp.tool()
    async def air_quality_health_check() -> Any:
        """
        Checks whether the IBB Air Quality API is accessible.
        Also reports the status of the Redis cache.
        """
        api_ok = await adapter.health_check()
        cache_ok = cache.is_connected

        return {
            "success": True,
            "api_status": {
                "ibb_air_quality": "online" if api_ok else "offline",
            },
            "cache_status": {
                "redis": "connected" if cache_ok else "disconnected (fallback mode)",
            },
        }
