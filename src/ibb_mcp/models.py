from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class AQIStation:
    """Standard model for air quality stations."""

    station_id: str
    name: str
    address: str
    latitude: float
    longitude: float
    source: str = "ibb_hava_kalitesi"

    def to_dict(self) -> dict:
        return {
            "station_id": self.station_id,
            "name": self.name,
            "address": self.address,
            "location": {
                "latitude": self.latitude,
                "longitude": self.longitude,
            },
            "source": self.source,
        }


@dataclass
class PollutantConcentration:
    """Pollutant concentration values."""

    pm10: float | None = None
    so2: float | None = None
    o3: float | None = None
    no2: float | None = None
    co: float | None = None

    def to_dict(self) -> dict:
        return {
            k: v
            for k, v in {
                "PM10": self.pm10,
                "SO2": self.so2,
                "O3": self.o3,
                "NO2": self.no2,
                "CO": self.co,
            }.items()
            if v is not None
        }


@dataclass
class AQIValue:
    """Air Quality Index (AQI) values."""

    pm10: float | None = None
    so2: float | None = None
    o3: float | None = None
    no2: float | None = None
    co: float | None = None
    overall_aqi: float | None = None
    dominant_pollutant: str | None = None
    status: str | None = None
    status_color: str | None = None

    def to_dict(self) -> dict:
        return {
            k: v
            for k, v in {
                "PM10": self.pm10,
                "SO2": self.so2,
                "O3": self.o3,
                "NO2": self.no2,
                "CO": self.co,
                "overall_aqi": self.overall_aqi,
                "dominant_pollutant": self.dominant_pollutant,
                "status": self.status,
                "status_color": self.status_color,
            }.items()
            if v is not None
        }


@dataclass
class AQIMeasurement:
    """Standard model for air quality measurement results."""

    station_id: str
    read_time: datetime
    concentration: PollutantConcentration
    aqi: AQIValue
    source: str = "ibb_hava_kalitesi"

    def to_dict(self) -> dict:
        return {
            "station_id": self.station_id,
            "read_time": self.read_time.isoformat(),
            "concentration": self.concentration.to_dict(),
            "aqi": self.aqi.to_dict(),
            "source": self.source,
        }


@dataclass
class MCPResponse:
    """Standard wrapper for MCP tool responses."""

    success: bool
    data: Any
    error: str | None = None
    cached: bool = False
    source: str = "unknown"
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        result = {
            "success": self.success,
            "source": self.source,
            "cached": self.cached,
        }
        if self.success:
            result["data"] = self.data
        else:
            result["error"] = self.error
        if self.extra:
            result.update(self.extra)
        return result
