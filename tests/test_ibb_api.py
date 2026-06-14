"""
IBB Air Quality API real integration tests.
Requires internet connection to run.
"""

import os
import sys
import asyncio
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ibb_mcp.adapters.ibb_air_quality import IBBAirQualityAdapter

IBB_BASE_URL = "https://api.ibb.gov.tr/havakalitesi/OpenDataPortalHandler"


async def test_get_stations():
    """Station list API test."""
    print("\n=== TEST: Station List ===")
    async with IBBAirQualityAdapter(base_url=IBB_BASE_URL) as adapter:
        stations = await adapter.get_stations()

    assert len(stations) > 0, "Station list is empty!"
    print(f"✅ {len(stations)} stations found")

    # Show the first station
    s = stations[0]
    print(f"   Sample Station:")
    print(f"   - ID: {s.station_id}")
    print(f"   - Name: {s.name}")
    print(f"   - Address: {s.address}")
    print(f"   - Coordinate: ({s.latitude}, {s.longitude})")
    print(f"   - Source: {s.source}")

    # Location data check (some stations might not have coordinates)
    valid_locations = [s for s in stations if s.latitude != 0.0]
    print(f"   Stations with valid coordinates: {len(valid_locations)}/{len(stations)}")

    return stations


async def test_get_measurements(station_id: str):
    """Measurement data API test."""
    print(f"\n=== TEST: Station Measurements [{station_id[:8]}...] ===")

    end_date = datetime.now()
    start_date = end_date - timedelta(days=1)

    async with IBBAirQualityAdapter(base_url=IBB_BASE_URL) as adapter:
        measurements = await adapter.get_measurements(station_id, start_date, end_date)

    if not measurements:
        print(
            f"⚠️   No measurements found for this station in the last 24 hours (common case)"
        )
        return []

    print(f"✅ {len(measurements)} measurements found")
    m = measurements[0]
    print(f"   Latest measurement time: {m.read_time}")
    print(f"   Concentration: {m.concentration.to_dict()}")
    print(f"   AQI: {m.aqi.to_dict()}")
    return measurements


async def test_health_check():
    """Health check test."""
    print("\n=== TEST: Health Check ===")
    async with IBBAirQualityAdapter(base_url=IBB_BASE_URL) as adapter:
        ok = await adapter.health_check()

    assert ok, "API is unreachable!"
    print("✅ API is accessible")


async def test_standard_model_format():
    """Standard model format check."""
    print("\n=== TEST: Standard Model Format ===")
    async with IBBAirQualityAdapter(base_url=IBB_BASE_URL) as adapter:
        stations = await adapter.get_stations()

    station_dict = stations[0].to_dict()
    required_keys = {"station_id", "name", "address", "location", "source"}
    missing = required_keys - set(station_dict.keys())
    assert not missing, f"Eksik alanlar: {missing}"
    assert "latitude" in station_dict["location"]
    assert "longitude" in station_dict["location"]
    print("✅ Standard model format is correct")
    print(f"   Sample output: {station_dict}")


async def main():
    print("IBB Air Quality API - Integration Tests")
    print("=" * 50)

    try:
        await test_health_check()
        stations = await test_get_stations()
        await test_standard_model_format()

        if stations:
            # Try the first few stations to find one with measurements
            for station in stations[:5]:
                measurements = await test_get_measurements(station.station_id)
                if measurements:
                    break

        print("\n" + "=" * 50)
        print("✅ All tests passed successfully!")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
