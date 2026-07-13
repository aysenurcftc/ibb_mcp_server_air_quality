# IBB Air Quality MCP Server

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![FastMCP](https://img.shields.io/badge/built%20with-FastMCP-orange)

An MCP (Model Context Protocol) server for the Istanbul Metropolitan Municipality (IBB) Air Quality Open Data API.
Built with FastMCP + Redis cache + Docker.

## How It Works

```
Claude Desktop (MCP client)
        │
        │  tool call (e.g. "get air quality in Maslak")
        ▼
FastMCP Server (this project)
        │
        ├─► Redis cache ──► cache hit? return cached data
        │                             │
        │                             ▼ (miss)
        └─► IBB Open Data API ──► fetch fresh data ──► store in Redis (layered TTL)
                                                              │
                                                              ▼
                                                     return result to Claude
```

1. Claude sends a tool request (e.g. station list, PM10 readings) to the MCP server.
2. The server checks Redis for a cached response.
3. On a cache miss, it queries the IBB Open Data API directly.
4. The response is cached in Redis and returned to Claude.

**Cache strategy:** TTL is layered by data volatility — station list (rarely changes) is cached for 24h, while measurements (updated hourly) are cached for 30–60 min.

## Quick Start

```bash
git clone https://github.com/aysenurcftc/ibb_mcp_server_air_quality.git
cd ibb_mcp_server_air_quality
cp .env.example .env
docker compose up -d
```

## Claude Desktop Setup

Add this to your `claude_desktop_config.json`:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "ibb": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/ibb-mcp-server", "ibb-mcp"],
      "env": {
        "MCP_TRANSPORT": "stdio",
        "REDIS_URL": "redis://localhost:6379/0",
        "STATIONS_CACHE_TTL": "86400",
        "MEASUREMENTS_CACHE_TTL": "1800",
        "IBB_HAVA_KALITESI_BASE_URL": "https://api.ibb.gov.tr/havakalitesi/OpenDataPortalHandler"
      }
    }
  }
}
```

> On Windows, use double backslashes in the path: `C:\\Users\\name\\projects\\ibb-mcp-server`
> Run `docker compose up -d` before opening Claude Desktop so Redis is available on `localhost:6379`.

## Available Tools

| Tool | Description |
|---|---|
| `get_air_quality_stations` | List all IBB air quality monitoring stations in Istanbul |
| `get_air_quality_measurements` | Get PM10, SO2, O3, NO2, CO readings for a station and date range (max 7 days) |
| `get_station_latest_status` | Get the latest reading for a station from the last 24 hours |
| `air_quality_health_check` | Check API and Redis connection status |

**Example queries:**
- "List air quality stations in Istanbul"
- "What is the current air quality at Maslak station?"
- "Get PM10 readings for Esenler station from January 15 to January 16, 2024"

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `STATIONS_CACHE_TTL` | `86400` | Cache duration for the station list, in seconds (24h) |
| `MEASUREMENTS_CACHE_TTL` | `1800` | Cache duration for measurement readings, in seconds (30 min) |
| `IBB_HAVA_KALITESI_BASE_URL` | `https://api.ibb.gov.tr/...` | IBB API base URL |
| `MCP_TRANSPORT` | `stdio` | `stdio` or `http` |
| `MCP_PORT` | `8000` | Port for HTTP mode |

## Developer Setup

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # macOS/Linux
uv sync

# Run in HTTP mode (for testing)
MCP_TRANSPORT=http uv run ibb-mcp
```

## Tests

```bash
uv run python tests/test_unit.py       # no internet required
uv run python tests/test_ibb_api.py    # requires internet
```


## License

MIT
