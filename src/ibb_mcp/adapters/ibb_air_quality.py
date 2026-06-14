"""
İBB Air Quality API Adapter.
"""

import logging
from datetime import datetime

from .base import BaseAdapter
from ..models import AQIMeasurement, AQIStation, AQIValue, PollutantConcentration

logger = logging.getLogger(__name__)


class IBBAirQualityAdapter(BaseAdapter):
    SOURCE_NAME = "ibb_hava_kalitesi"

    def __init__(self, base_url: str):
        super().__init__(base_url=base_url, api_key=None)

    async def health_check(self) -> bool:
        try:
            data = await self.get("/GetAQIStations")
            return isinstance(data, list) and len(data) > 0
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    async def get_stations(self) -> list[AQIStation]:
        raw_stations = await self.get("/GetAQIStations")
        stations = []
        for raw in raw_stations:
            try:
                station = self._parse_station(raw)
                if station:
                    stations.append(station)
            except Exception as e:
                logger.warning(f"Station parsing error [{raw.get('Id')}]: {e}")
        logger.info(f"{len(stations)} stations loaded")
        return stations

    async def get_measurements(
        self,
        station_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[AQIMeasurement]:
        date_fmt = "%d.%m.%Y %H:%M:%S"
        params = {
            "StationId": station_id,
            "StartDate": start_date.strftime(date_fmt),
            "EndDate": end_date.strftime(date_fmt),
        }
        raw_measurements = await self.get("/GetAQIByStationId", params=params)
        if not isinstance(raw_measurements, list):
            return []
        measurements = []
        for raw in raw_measurements:
            try:
                m = self._parse_measurement(station_id, raw)
                if m:
                    measurements.append(m)
            except Exception as e:
                logger.warning(f"Measurement parsing error: {e}")
        logger.info(f"{len(measurements)} measurements loaded for {station_id}")
        return measurements

    def _parse_station(self, raw: dict) -> AQIStation | None:
        station_id = raw.get("Id", "").strip()
        name = raw.get("Name", "").strip()
        address = raw.get("Adress", raw.get("Address", "")).strip()
        location_str = raw.get("Location", "")
        if not station_id or not name:
            return None
        lat, lon = self._parse_location(location_str)
        return AQIStation(
            station_id=station_id,
            name=name,
            address=address,
            latitude=lat,
            longitude=lon,
            source=self.SOURCE_NAME,
        )

    def _parse_measurement(self, station_id: str, raw: dict) -> AQIMeasurement | None:
        read_time_str = raw.get("ReadTime", "")
        if not read_time_str:
            return None
        read_time = self._parse_datetime(read_time_str)
        if not read_time:
            return None
        conc_raw = raw.get("Concentration", {}) or {}
        concentration = PollutantConcentration(
            pm10=self._safe_float(conc_raw.get("PM10")),
            so2=self._safe_float(conc_raw.get("SO2")),
            o3=self._safe_float(conc_raw.get("O3")),
            no2=self._safe_float(conc_raw.get("NO2")),
            co=self._safe_float(conc_raw.get("CO")),
        )
        aqi_raw = raw.get("AQI", {}) or {}
        aqi = AQIValue(
            pm10=self._safe_float(aqi_raw.get("PM10")),
            so2=self._safe_float(aqi_raw.get("SO2")),
            o3=self._safe_float(aqi_raw.get("O3")),
            no2=self._safe_float(aqi_raw.get("NO2")),
            co=self._safe_float(aqi_raw.get("CO")),
            overall_aqi=self._safe_float(aqi_raw.get("HKI") or aqi_raw.get("AQI")),
            dominant_pollutant=aqi_raw.get("DominantPollutant")
            or aqi_raw.get("Kirletici"),
            status=aqi_raw.get("Status") or aqi_raw.get("Durum"),
            status_color=aqi_raw.get("Color") or aqi_raw.get("Renk"),
        )
        return AQIMeasurement(
            station_id=station_id,
            read_time=read_time,
            concentration=concentration,
            aqi=aqi,
            source=self.SOURCE_NAME,
        )

    @staticmethod
    def _parse_location(location_str: str) -> tuple[float, float]:
        """
        Supports two formats:
         "POINT (29.024512 41.100072)" -> Format from the API (lon lat order)
         "41.0820,29.0500"             -> lat,lon format
        """
        try:
            s = location_str.strip()
            if s.upper().startswith("POINT"):
                inner = s[s.index("(") + 1 : s.index(")")]
                parts = inner.strip().split()
                if len(parts) == 2:
                    lon, lat = float(parts[0]), float(parts[1])
                    return lat, lon
            else:
                parts = s.replace(" ", "").split(",")
                if len(parts) >= 2:
                    return float(parts[0]), float(parts[1])
        except (ValueError, AttributeError, IndexError):
            pass

        return 0.0, 0.0

    @staticmethod
    def _parse_datetime(dt_str: str) -> datetime | None:
        formats = [
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%d.%m.%Y %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(dt_str.strip(), fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _safe_float(value) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
