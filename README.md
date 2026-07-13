# IBB Air Quality MCP Server

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![FastMCP](https://img.shields.io/badge/built%20with-FastMCP-orange)

MCP server for the Istanbul Metropolitan Municipality (IBB) Air Quality Open Data API.
Built with FastMCP + Redis cache + Docker.

## How It Works

```
Claude Desktop ──tool call──► FastMCP Server ──► Redis cache
                                     │              │ hit → return
                                     │ miss         │
                                     ▼              │
                              IBB Open Data API ────┘ (caches result, returns to Claude)
```

Cache TTL is layered by data volatility: station list (rarely changes) → 24h, measurements (hourly updates) → 30–60 min.

## Quick Start

```bash
git clone https://github.com/aysenurcftc/ibb_mcp_server_air_quality.git
cd ibb_mcp_server_air_quality
cp .env.example .env
docker compose up -d
```

## Claude Desktop Setup

Add to `claude_desktop_config.json`:
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "ibb": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/ibb_mcp_server_air_quality", "ibb-mcp"],
      "env": {
        "MCP_TRANSPORT": "stdio",
        "REDIS_URL": "redis://localhost:6379/0",
        "IBB_HAVA_KALITESI_BASE_URL": "https://api.ibb.gov.tr/havakalitesi/OpenDataPortalHandler"
      }
    }
  }
}
```
> Windows'ta yolda çift ters slash kullanın: `C:\\Users\\name\\projects\\ibb_mcp_server_air_quality`

## Available Tools

| Tool | Description |
|---|---|
| `get_air_quality_stations` | List all IBB air quality monitoring stations |
| `get_nearest_station` | Find the nearest station to a given lat/lon, with distance in km |
| `get_air_quality_measurements` | PM10, SO2, O3, NO2, CO readings for a station/date range (max 7 days) |
| `get_station_latest_status` | Latest reading for a station (last 24h) |
| `air_quality_health_check` | API and Redis connection status |


## Resources

| Resource | Description |
|---|---|
| `ibb://air-quality/stations` | Static station list (name, address, coordinates) as JSON |

## Developer Setup

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # macOS/Linux
uv sync
MCP_TRANSPORT=http uv run ibb-mcp   # HTTP mode (test için)
```

## Tests

```bash
uv run python tests/test_unit.py       # internet gerekmez
uv run python tests/test_ibb_api.py    # internet gerekir
```

## License

MIT
