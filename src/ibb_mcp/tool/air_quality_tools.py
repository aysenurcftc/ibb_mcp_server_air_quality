import logging
import math
from datetime import datetime, timedelta
from typing import Any

from ..adapters.base import AdapterError
from ..adapters.ibb_air_quality import IBBAirQualityAdapter
from ..cache.redis_cache import RedisCache
from ..models import MCPResponse

logger = logging.getLogger(__name__)

# --- Layered Cache TTL Strategy ---
# Station list (name, address, location) barely changes -> long TTL.
# Measurement data updates hourly -> medium TTL.
STATIONS_TTL = 86_400       # 24 hours
MEASUREMENTS_TTL = 1_800    # 30 minutes
LATEST_STATUS_TTL = 1_800   # 30 minutes


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates the distance between two coordinates in kilometers."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


async def _get_or_fetch_stations(
    adapter: IBBAirQualityAdapter, cache: RedisCache
) -> tuple[list[dict], bool]:
    """Shared function to retrieve station list (shared by tool + resource + get_nearest_station).
    Returns (data, was_cached)."""
    cache_key = cache.make_key("station", "all")
    cached = await cache.get(cache_key)
    if cached:
        return cached, True
    stations = await adapter.get_stations()
    data = [s.to_dict() for s in stations]
    await cache.set(cache_key, data, ttl=STATIONS_TTL)
    return data, False


def register_air_quality_tools(mcp, adapter: IBBAirQualityAdapter, cache: RedisCache):
    """
    Register air quality tools, resources and prompts to the MCP server.

    Args:
        mcp: FastMCP server instance
        adapter: IBB adapter
        cache: Redis cache manager
    """

    # ------------------------------------------------------------------
    # TOOLS
    # ------------------------------------------------------------------

    @mcp.tool()
    async def get_air_quality_stations() -> Any:
        """
        Returns a list of all air quality measuring stations in Istanbul.
        Includes the name, address, and coordinates of each station.
        Results are cached for 24 hours (station list rarely changes).
        """
        try:
            data, was_cached = await _get_or_fetch_stations(adapter, cache)
            return MCPResponse(
                success=True,
                data=data,
                cached=was_cached,
                source=adapter.SOURCE_NAME,
                extra={"count": len(data)},
            ).to_dict()
        except AdapterError as e:
            logger.error(f"Failed to retrieve station list: {e}")
            return MCPResponse(
                success=False, data=None, error=str(e), source=adapter.SOURCE_NAME
            ).to_dict()

    @mcp.tool()
    async def get_nearest_station(latitude: float, longitude: float) -> Any:
        """
        Finds the nearest air quality station to the given latitude/longitude
        and returns the distance in kilometers. Used as a first step for
        air quality queries based on user location.

        Args:
            latitude: Latitude (e.g., 41.0369 - around Maslak)
            longitude: Longitude (e.g., 29.0075)
        """
        try:
            stations, _ = await _get_or_fetch_stations(adapter, cache)
        except AdapterError as e:
            return MCPResponse(
                success=False, data=None, error=str(e), source=adapter.SOURCE_NAME
            ).to_dict()

        candidates = [
            s for s in stations
            if s["location"]["latitude"] and s["location"]["longitude"]
        ]
        if not candidates:
            return MCPResponse(
                success=False,
                data=None,
                error="No stations found with valid location information.",
                source=adapter.SOURCE_NAME,
            ).to_dict()

        nearest = min(
            candidates,
            key=lambda s: _haversine_km(
                latitude, longitude, s["location"]["latitude"], s["location"]["longitude"]
            ),
        )
        distance_km = round(
            _haversine_km(
                latitude, longitude, nearest["location"]["latitude"], nearest["location"]["longitude"]
            ),
            2,
        )

        return MCPResponse(
            success=True,
            data={**nearest, "distance_km": distance_km},
            cached=True,
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
            await cache.set(cache_key, data, ttl=MEASUREMENTS_TTL)
            return MCPResponse(
                success=True,
                data=data,
                cached=False,
                source=adapter.SOURCE_NAME,
                extra={"count": len(data), "station_id": station_id},
            ).to_dict()
        except AdapterError as e:
            logger.error(f"Failed to retrieve measurement data [{station_id}]: {e}")
            return MCPResponse(
                success=False, data=None, error=str(e), source=adapter.SOURCE_NAME
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
            await cache.set(cache_key, data, ttl=LATEST_STATUS_TTL)
            return MCPResponse(
                success=True, data=data, cached=False, source=adapter.SOURCE_NAME
            ).to_dict()
        except AdapterError as e:
            logger.error(f"Failed to retrieve latest status [{station_id}]: {e}")
            return MCPResponse(
                success=False, data=None, error=str(e), source=adapter.SOURCE_NAME
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
            "api_status": {"ibb_air_quality": "online" if api_ok else "offline"},
            "cache_status": {
                "redis": "connected" if cache_ok else "disconnected (fallback mode)"
            },
        }

    # ------------------------------------------------------------------
    # RESOURCES — Static or rarely changing data that the LLM can read
    # directly without invoking a tool call.
    # ------------------------------------------------------------------

    @mcp.resource(
        "ibb://air-quality/stations",
        name="air_quality_stations",
        description="Static list of all air quality stations in Istanbul (name, address, coordinates).",
        mime_type="application/json",
    )
    async def stations_resource() -> list[dict]:
        data, _ = await _get_or_fetch_stations(adapter, cache)
        return data

    # ------------------------------------------------------------------
    # PROMPTS — Ready-made templates for the LLM.
    # ------------------------------------------------------------------

    @mcp.prompt(
        name="hava_kalitesi_ozeti",
        description="Compares two stations and generates a health warning text for sensitive groups.",
    )
    def hava_kalitesi_ozeti(station_a: str, station_b: str) -> str:
        """
        Args:
            station_a: First station name (e.g., 'Maslak')
            station_b: Second station name (e.g., 'Kadıköy')
        """
        return (
            f"Fetch the current air quality data for '{station_a}' and '{station_b}' stations "
            f"using the get_air_quality_stations and get_station_latest_status tools. "
            f"Then compare the two stations in terms of PM10, NO2, and overall AQI values, and "
            f"write an easy-to-understand health warning text in Turkish for sensitive groups "
            f"with respiratory conditions such as asthma or COPD. Clearly state around which station "
            f"spending time outdoors is more risky."
        )