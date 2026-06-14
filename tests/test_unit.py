"""
IBB Air Quality Adapter - Unit Tests (with Mock).
Does not require connection to the real API.
"""

import asyncio
import json
import sys
import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ibb_mcp.adapters.ibb_air_quality import IBBAirQualityAdapter
from ibb_mcp.cache.redis_cache import RedisCache
from ibb_mcp.models import AQIStation, AQIMeasurement

IBB_BASE_URL = "https://api.ibb.gov.tr/havakalitesi/OpenDataPortalHandler"

# --- Mock ---

MOCK_STATIONS_RESPONSE = [
    {
        "Id": "377e1216-bcc7-42c0-aad8-4d5b3d602b78",
        "Name": "Beşiktaş",
        "Adress": "Beşiktaş Meydanı, İstanbul",
        "Location": "41.0422,29.0061",
    },
    {
        "Id": "aaaabbbb-cccc-dddd-eeee-ffffffffffff",
        "Name": "Kadıköy",
        "Adress": "Kadıköy Meydanı, İstanbul",
        "Location": "40.9907,29.0230",
    },
]

MOCK_MEASUREMENTS_RESPONSE = [
    {
        "ReadTime": "2024-01-15T10:00:00",
        "Concentration": {
            "PM10": 45.2,
            "SO2": 12.1,
            "O3": 68.0,
            "NO2": 38.5,
            "CO": 0.8,
        },
        "AQI": {
            "PM10": 42.0,
            "SO2": 10.0,
            "O3": 55.0,
            "NO2": 30.0,
            "CO": 5.0,
            "HKI": 55.0,
            "Kirletici": "O3",
            "Durum": "Orta",
            "Renk": "#FFFF00",
        },
    },
    {
        "ReadTime": "2024-01-15T11:00:00",
        "Concentration": {
            "PM10": 50.1,
            "SO2": 14.3,
            "O3": None,
            "NO2": 40.0,
            "CO": 0.9,
        },
        "AQI": {
            "PM10": 48.0,
            "SO2": 12.0,
            "O3": None,
            "NO2": 33.0,
            "CO": 6.0,
            "HKI": 48.0,
            "Kirletici": "PM10",
            "Durum": "İyi",
            "Renk": "#00FF00",
        },
    },
]


async def test_parse_stations():
    """Test that station data is correctly parsed."""
    print("\n=== TEST: Station Parse ===")
    adapter = IBBAirQualityAdapter(base_url=IBB_BASE_URL)

    with patch.object(
        adapter, "get", new=AsyncMock(return_value=MOCK_STATIONS_RESPONSE)
    ):
        await adapter.connect()
        stations = await adapter.get_stations()
        await adapter.disconnect()

    assert len(stations) == 2, f"Expected 2 stations, received: {len(stations)}"

    s1 = stations[0]
    assert s1.station_id == "377e1216-bcc7-42c0-aad8-4d5b3d602b78"
    assert s1.name == "Beşiktaş"
    assert s1.address == "Beşiktaş Meydanı, İstanbul"
    assert abs(s1.latitude - 41.0422) < 0.0001
    assert abs(s1.longitude - 29.0061) < 0.0001
    assert s1.source == "ibb_hava_kalitesi"

    print(f"✅ {len(stations)} stations parsed")
    print(f"   {s1.name}: ({s1.latitude}, {s1.longitude})")


async def test_parse_measurements():
    """Test that measurement data is correctly parsed."""
    print("\n=== TEST: Measurement Parse ===")
    adapter = IBBAirQualityAdapter(base_url=IBB_BASE_URL)

    station_id = "377e1216-bcc7-42c0-aad8-4d5b3d602b78"
    start = datetime(2024, 1, 15, 0, 0, 0)
    end = datetime(2024, 1, 16, 0, 0, 0)

    with patch.object(
        adapter, "get", new=AsyncMock(return_value=MOCK_MEASUREMENTS_RESPONSE)
    ):
        await adapter.connect()
        measurements = await adapter.get_measurements(station_id, start, end)
        await adapter.disconnect()

    assert len(measurements) == 2

    m1 = measurements[0]
    assert m1.station_id == station_id
    assert m1.read_time == datetime(2024, 1, 15, 10, 0, 0)
    assert m1.concentration.pm10 == 45.2
    assert m1.concentration.o3 == 68.0
    assert m1.aqi.overall_aqi == 55.0
    assert m1.aqi.dominant_pollutant == "O3"
    assert m1.aqi.status == "Orta"

    m2 = measurements[1]
    assert m2.concentration.o3 is None
    assert m2.aqi.o3 is None

    print(f"✅ {len(measurements)} measurements parsed")
    print(f"   AQI: {m1.aqi.overall_aqi}, Pollutant: {m1.aqi.dominant_pollutant}")


async def test_standard_model_serialization():
    """Test the correctness of to_dict() outputs."""
    print("\n=== TEST: Standard Model Serialization ===")
    adapter = IBBAirQualityAdapter(base_url=IBB_BASE_URL)

    with patch.object(
        adapter, "get", new=AsyncMock(return_value=MOCK_STATIONS_RESPONSE)
    ):
        await adapter.connect()
        stations = await adapter.get_stations()
        await adapter.disconnect()

    d = stations[0].to_dict()
    assert "station_id" in d
    assert "name" in d
    assert "address" in d
    assert "location" in d
    assert "latitude" in d["location"]
    assert "longitude" in d["location"]
    assert "source" in d

    print(f"✅ Standard model format is correct")
    print(f"   Output: {json.dumps(d, ensure_ascii=False, indent=2)}")


async def test_location_parse_edge_cases():
    """Location string parse edge cases."""
    print("\n=== TEST: Location Parse Edge Cases ===")
    adapter = IBBAirQualityAdapter(base_url=IBB_BASE_URL)

    # Normal
    lat, lon = adapter._parse_location("41.0422,29.0061")
    assert abs(lat - 41.0422) < 0.0001
    assert abs(lon - 29.0061) < 0.0001

    lat, lon = adapter._parse_location("41.0422, 29.0061")
    assert abs(lat - 41.0422) < 0.0001

    lat, lon = adapter._parse_location("")
    assert lat == 0.0 and lon == 0.0

    lat, lon = adapter._parse_location("invalid")
    assert lat == 0.0 and lon == 0.0

    print(f"✅ Location parse edge cases are correct")


async def test_cache_integration():
    """Test that the cache works properly (without Redis)."""
    print("\n=== TEST: Cache Integration ===")

    cache = RedisCache(redis_url="redis://localhost:6379/0", default_ttl=60)
    # No Redis, testing in offline/disconnected mode.
    await cache.connect()  # Does not raise an error, returns None.

    # Get without cache always returns None.
    result = await cache.get("test:key")
    assert result is None, "Disconnected cache should return None"

    # set should not raise an error either
    await cache.set("test:key", {"data": "value"})

    key = cache.make_key("stations", "all")
    assert key == "ibb_mcp:stations:all"

    print("✅ Cache fallback mode is working correctly")


async def test_date_parsing():
    """Date format parsing tests."""
    print("\n=== TEST: Date Parse ===")
    adapter = IBBAirQualityAdapter(base_url=IBB_BASE_URL)

    cases = [
        ("2024-01-15T10:00:00", datetime(2024, 1, 15, 10, 0, 0)),
        ("2024-01-15 10:00:00", datetime(2024, 1, 15, 10, 0, 0)),
        ("15.01.2024 10:00:00", datetime(2024, 1, 15, 10, 0, 0)),
    ]
    for raw, expected in cases:
        result = adapter._parse_datetime(raw)
        assert result == expected, f"{raw!r} → {result} (expected {expected})"

    assert adapter._parse_datetime("invalid") is None
    print("✅ Date parse is correct")


async def main():
    print("IBB Air Quality Adapter - Unit Tests")
    print("=" * 50)

    tests = [
        test_parse_stations,
        test_parse_measurements,
        test_standard_model_serialization,
        test_location_parse_edge_cases,
        test_cache_integration,
        test_date_parsing,
    ]

    failed = 0
    for test in tests:
        try:
            await test()
        except Exception as e:
            print(f"❌ {test.__name__}: {e}")
            import traceback

            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 50)
    if failed == 0:
        print(f"✅ All {len(tests)} tests passed successfully!")
    else:
        print(f"❌ {failed}/{len(tests)} tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
